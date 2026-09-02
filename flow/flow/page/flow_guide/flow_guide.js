frappe.pages["flow-guide"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Flow Guide"),
		single_column: true,
	});

	const container = $(wrapper).find(".layout-main-section");
	container.empty().addClass("flow-guide-page");
	renderGuide(container);
};

function renderGuide(container) {
	const features = [
		{
			icon: "message-circle",
			title: __("AI Chat"),
			description: __("Ask a question in normal language. Flow can find permitted information, explain it, and help complete a task."),
			example: __("Example: Show unpaid sales invoices due this week."),
			howTo: [
				__("Open Flow Chat and choose an agent from the selector beside the message box."),
				__("Type your request with useful details such as the company, date range, or status, then send it."),
				__("Review the answer and approve or deny any action when Flow asks."),
			],
		},
		{
			icon: "users",
			title: __("Specialised Agents"),
			description: __("Choose an agent for the type of work you need. Each agent has focused instructions and access to selected tools."),
			example: __("Example: Use the Sales Analysis Agent for sales questions."),
			howTo: [
				__("Open Agent from the Flow sidebar to see the available featured and custom agents."),
				__("Create an agent when needed by choosing a model and writing clear instructions for its role and limits."),
				__("Return to Chat and select that agent before sending your request."),
			],
		},
		{
			icon: "tool",
			title: __("Tools and Permissions"),
			description: __("Tools let an agent read reports, find records, or make approved changes. Your Frappe permissions still apply."),
			example: __("Flow cannot use a tool to access a record that you cannot access."),
			howTo: [
				__("Choose an agent in Chat, then select the sliders icon beside the agent selector."),
				__("Set each tool to Always Allow, Needs Approval, or Blocked."),
				__("When an approval request appears in chat, check the proposed action before approving it."),
			],
		},
		{
			icon: "book-open",
			title: __("Knowledge"),
			description: __("Knowledge gives an agent trusted reference material. This helps it answer from selected sources instead of unrelated data."),
			example: __("Example: Answer a policy question from your company handbook."),
			howTo: [
				__("Open Knowledge Base from the Flow sidebar and create a base with a clear description."),
				__("Add a Flow Knowledge Source using text, a file, a URL, or selected DocType records."),
				__("After the source status is Completed, ask an agent that has access to that knowledge base."),
			],
		},
		{
			icon: "zap",
			title: __("Triggers"),
			description: __("A trigger starts an agent automatically when a document changes or when a schedule becomes due."),
			example: __("Example: Review a new Lead after it is created."),
			howTo: [
				__("Open Triggers from the Flow sidebar and create a Flow Trigger."),
				__("Choose an agent and either a DocType event or a scheduled cron expression."),
				__("Add an optional condition, write the prompt template, enable the trigger, and save it."),
			],
		},
		{
			icon: "layers",
			title: __("Macros"),
			description: __("A macro saves one or more prompts as a reusable task. Run it again without writing the same instructions."),
			example: __("Example: Save your weekly overdue invoice check."),
			howTo: [
				__("From a useful chat, open Action and select Save as macro, or open Macro and create one."),
				__("Choose the agent, add the prompts in the order they should run, and save."),
				__("Select Run whenever needed, or enable a schedule for automatic runs."),
			],
		},
		{
			icon: "chart",
			title: __("Reports"),
			description: __("Flow can explain required report filters, run a permitted Frappe report, and summarize the result."),
			example: __("Example: Run a sales report for the current month."),
			howTo: [
				__("In Chat, choose an agent that has report tools and ask for the report by name or business purpose."),
				__("Include known filters such as company and period; Flow will ask for any required values that are missing."),
				__("Ask Flow to summarize, compare, or explain the returned results."),
			],
		},
		{
			icon: "download",
			title: __("Excel Export"),
			description: __("Flow can put suitable table data into an Excel file. It stores the file in Frappe and returns a download link."),
			example: __("Example: Export the invoice list to Excel."),
			howTo: [
				__("Ask an agent with export access to export records or report results to Excel."),
				__("State the filters and columns you need, and approve the tool call if prompted."),
				__("When the export finishes, select the download link in Flow's reply."),
			],
		},
	];

	const page = $("<div>").addClass("flow-guide-app").appendTo(container);
	renderHeader(page);
	const shell = $("<main>").addClass("flow-guide-shell").appendTo(page);

	const hero = $("<section>").addClass("flow-guide-hero").appendTo(shell);
	$("<div>").addClass("flow-guide-eyebrow").text(__("FLOW HELP CENTRE")).appendTo(hero);
	$("<h1>").text(__("Meet Flow, your assistant inside Frappe")).appendTo(hero);
	$("<p>")
		.text(__("Flow helps you ask questions, understand business information, and complete routine work. You can use normal language instead of finding every screen or report yourself."))
		.appendTo(hero);
	const heroActions = $("<div>").addClass("flow-guide-hero-actions").appendTo(hero);
	makeButton(heroActions, __("Start a chat"), "message-circle", () => openChat(), true);

	renderSteps(shell);

	const section = $("<section>").addClass("flow-guide-section").appendTo(shell);
	$("<h2>").text(__("What Flow can help you do")).appendTo(section);
	$("<p>")
		.addClass("flow-guide-section-copy")
		.text(__("Your administrator chooses which agents, tools, and knowledge sources are available."))
		.appendTo(section);

	const grid = $("<div>").addClass("flow-guide-grid").appendTo(section);
	features.forEach((feature) => renderFeature(grid, feature));

	const note = $("<section>").addClass("flow-guide-note").appendTo(shell);
	$(frappe.utils.icon("shield", "md")).appendTo(note);
	const noteCopy = $("<div>").appendTo(note);
	$("<h3>").text(__("You stay in control")).appendTo(noteCopy);
	$("<p>")
		.text(__("Flow uses your Frappe permissions when a tool reads or changes data. A sensitive action can also ask for confirmation before it continues."))
		.appendTo(noteCopy);

	renderExamples(shell);
}

function renderHeader(page) {
	const header = $("<header>").addClass("flow-guide-header").appendTo(page);
	const brand = $("<div>").addClass("flow-guide-brand").appendTo(header);
	$(frappe.utils.icon("help", "md")).appendTo(brand);
	$("<span>").text(__("Flow Guide")).appendTo(brand);
	makeButton(header, __("Open Flow Chat"), "message-circle", () => openChat());
}

function renderSteps(shell) {
	const steps = [
		__("Choose an agent that matches your task."),
		__("Write what you need in normal language."),
		__("Review the answer and any requested action."),
		__("Approve the action when Flow asks for confirmation."),
	];
	const section = $("<section>").addClass("flow-guide-section").appendTo(shell);
	$("<h2>").text(__("How Flow works")).appendTo(section);
	$("<p>")
		.addClass("flow-guide-section-copy")
		.text(__("You can start with a simple request. Flow guides the task from there."))
		.appendTo(section);
	const list = $("<ol>").addClass("flow-guide-steps").appendTo(section);
	steps.forEach((step, index) => {
		const item = $("<li>").appendTo(list);
		$("<span>").addClass("flow-guide-step-number").text(index + 1).appendTo(item);
		$("<span>").text(step).appendTo(item);
	});
}

function renderExamples(shell) {
	const examples = [
		__("Which customers have overdue invoices?"),
		__("Summarize sales for this month."),
		__("Show purchase orders waiting for delivery."),
		__("Export these results to Excel."),
	];
	const section = $("<section>").addClass("flow-guide-section").appendTo(shell);
	$("<h2>").text(__("Try asking")).appendTo(section);
	const list = $("<div>").addClass("flow-guide-prompts").appendTo(section);
	examples.forEach((example) => {
		const item = $("<button>").attr("type", "button").appendTo(list);
		$(frappe.utils.icon("arrow-up-right", "sm")).appendTo(item);
		$("<span>").text(example).appendTo(item);
		item.on("click", () => openChat(example));
	});
}

function renderFeature(grid, feature) {
	const card = $("<article>").addClass("flow-guide-card").appendTo(grid);
	const icon = $("<div>").addClass("flow-guide-card-icon").appendTo(card);
	$(frappe.utils.icon(feature.icon, "md")).appendTo(icon);
	$("<h3>").text(feature.title).appendTo(card);
	$("<p>").text(feature.description).appendTo(card);
	$("<p>").addClass("flow-guide-example").text(feature.example).appendTo(card);
	const howTo = $("<div>").addClass("flow-guide-how-to").appendTo(card);
	$("<h4>").text(__("How to use")).appendTo(howTo);
	const steps = $("<ol>").appendTo(howTo);
	feature.howTo.forEach((step) => $("<li>").text(step).appendTo(steps));
}

function makeButton(parent, label, icon, onClick, primary = false) {
	const button = $("<button>")
		.attr("type", "button")
		.addClass(primary ? "flow-guide-button is-primary" : "flow-guide-button")
		.appendTo(parent);
	$(frappe.utils.icon(icon, "sm")).appendTo(button);
	$("<span>").text(label).appendTo(button);
	button.on("click", onClick);
}

function openChat(prompt = "") {
	frappe.set_route("flow-chat");
	if (prompt) fillChatPrompt(prompt);
}

function fillChatPrompt(prompt, attempt = 0) {
	const input = document.querySelector("#flow-root .flow-composer textarea");
	if (!input) {
		if (attempt < 80) setTimeout(() => fillChatPrompt(prompt, attempt + 1), 100);
		return;
	}

	const setValue = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
	setValue.call(input, prompt);
	input.dispatchEvent(new Event("input", { bubbles: true }));
	input.focus();
}
