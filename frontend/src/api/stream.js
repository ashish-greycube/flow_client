import { serverMessage } from "./client";
import { __ } from "@/lib/translate";

const RUN_EVENT = "flow_run_event";
const POLL_INTERVAL_MS = 2000;
// Consecutive polls that must find the job gone, with no closing event, before the
// turn is given up on — one poll can land in the gap between the job's last event
// and the run's final save.
const DEAD_POLLS = 2;

// Starts a turn and hands each of its events to `onEvent`. The server picks the
// transport: a background job (JSON reply — follow it with followRun) when a worker
// is available, else the run streamed over this request as SSE `data:` blocks.
async function postStream(method, body, onEvent, signal) {
	const resp = await fetch(`/api/method/${method}`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"X-Frappe-CSRF-Token": frappe.csrf_token,
		},
		body: JSON.stringify({ ...body, stream: true, background: true }),
		signal,
	});
	if (!resp.ok) {
		const data = await resp.json().catch(() => ({}));
		throw new Error(serverMessage(data) || __("Request failed ({0})", [resp.status]));
	}
	if ((resp.headers.get("Content-Type") || "").includes("application/json")) {
		const { message } = await resp.json();
		if (message.event) onEvent(message.event);
		return followRun(message.name, message.stream, onEvent, signal);
	}
	if (!resp.body) {
		throw new Error(__("Request failed ({0})", [resp.status]));
	}

	const reader = resp.body.getReader();
	const decoder = new TextDecoder();
	let buffer = "";

	for (;;) {
		const { done, value } = await reader.read();
		if (done) break;
		buffer += decoder.decode(value, { stream: true });

		const blocks = buffer.split("\n\n");
		buffer = blocks.pop();
		for (const block of blocks) {
			const line = block.split("\n").find((l) => l.startsWith("data: "));
			if (line) onEvent(JSON.parse(line.slice(6)));
		}
	}
}

// Follows a run executing in a background job until it ends. Events are pushed over
// realtime and also fetched by polling, so text streams smoothly when the socket is
// up and nothing is lost when it isn't; `seq` keeps the two sources in order and
// free of duplicates. Rejects with an AbortError when `signal` aborts.
export function followRun(run, stream, onEvent, signal) {
	return new Promise((resolve, reject) => {
		const waiting = new Map();
		let seq = 0;
		let deadPolls = 0;
		let timer = null;
		let finished = false;

		const finish = (error) => {
			if (finished) return;
			finished = true;
			clearTimeout(timer);
			frappe.realtime?.off?.(RUN_EVENT, deliver);
			signal?.removeEventListener("abort", onAbort);
			if (error) reject(error);
			else resolve();
		};

		function deliver(record) {
			if (finished || !record || record.run !== run || record.stream !== stream) return;
			if (record.seq <= seq) return;
			waiting.set(record.seq, record.event);
			while (!finished && waiting.has(seq + 1)) {
				const event = waiting.get(seq + 1);
				waiting.delete(seq + 1);
				seq += 1;
				onEvent(event);
				if (event.type === "done" || event.type === "error") finish();
			}
		}

		function onAbort() {
			finish(new DOMException("Aborted", "AbortError"));
		}

		async function poll() {
			if (finished) return;
			try {
				const query = new URLSearchParams({ run_name: run, stream, after: seq });
				const resp = await fetch(`/api/method/flow.api.get_run_events?${query}`);
				if (resp.ok) {
					const { message } = await resp.json();
					for (const record of message.events) deliver(record);
					deadPolls = message.alive ? 0 : deadPolls + 1;
					if (!finished && deadPolls >= DEAD_POLLS) {
						// The job is gone without a closing event (worker killed, events expired).
						if (message.status === "Completed") {
							onEvent({ type: "done", status: "Completed", resync: true });
						} else {
							onEvent({
								type: "error",
								message:
									message.error ||
									__("The run stopped unexpectedly. Reload the chat to check its result."),
							});
						}
						finish();
					}
				}
			} catch {
				// A network blip: keep polling.
			}
			if (!finished) timer = setTimeout(poll, POLL_INTERVAL_MS);
		}

		if (signal?.aborted) return onAbort();
		signal?.addEventListener("abort", onAbort);
		frappe.realtime?.on?.(RUN_EVENT, deliver);
		poll();
	});
}

export const startRun = (body, onEvent, signal) =>
	postStream("flow.api.start_run", body, onEvent, signal);
export const resumeRun = (body, onEvent, signal) =>
	postStream("flow.api.resume_run", body, onEvent, signal);
