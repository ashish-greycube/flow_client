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
	const page = $("<div>").addClass("flow-guide-app").appendTo(container);
	renderHeader(page);

	const shell = $("<div>").addClass("flow-guide-shell").appendTo(page);
	const nav = $("<nav>").addClass("flow-guide-nav").attr("aria-label", __("Contents")).appendTo(shell);
	const article = $("<article>").addClass("flow-guide-doc").appendTo(shell);

	const chapters = guideChapters();
	renderIntro(article);
	chapters.forEach((chapter) => renderChapter(article, chapter));
	renderNav(nav, chapters);
	watchActiveTopic(article, nav);
}

function guideChapters() {
	return [
		{
			id: "getting-started",
			title: __("Getting started"),
			topics: [
				{
					id: "quick-start",
					title: __("Quick start"),
					body: __("You can start with a simple request. Flow guides the task from there."),
					steps: [
						__("Leave the agent on Auto, or choose one that matches your task."),
						__("Write what you need in normal language."),
						__("Review the answer and any requested action."),
						__("Approve the action when Flow asks for confirmation."),
					],
					action: { label: __("Open Flow Chat"), icon: "message-circle", onClick: () => openChat() },
				},
			],
		},
		{
			id: "setup",
			title: __("Set up Flow"),
			badge: __("For System Managers"),
			intro: __("Do this once per site, before anyone can chat. Connect an AI service with a Flow Provider, then add the Flow Model that agents will use."),
			topics: [
				{
					id: "flow-provider",
					title: __("1. Add a Flow Provider"),
					body: __("A provider stores the API key for one AI service. Every model from that service uses it, so you enter the key only once."),
					doctype: "Flow Provider",
					steps: [
						__("Open Flow Provider and select Add Flow Provider."),
						__("Enter the provider name in lowercase, such as openai, anthropic, gemini, or openrouter. Flow rejects names it does not recognise."),
						__("Paste the API key from that service, keep Enabled ticked, and save."),
					],
					fields: [
						[__("Provider"), __("Service name, for example anthropic. It also becomes the record name.")],
						[__("API Key"), __("Secret key from the service. Leave empty for local servers such as Ollama or LM Studio.")],
						[__("Base URL"), __("Optional. Only for a proxy, gateway, or self-hosted endpoint.")],
						[__("Extra Params"), __("Optional JSON sent with every call, for example {\"api_version\": \"2024-02-01\"} for Azure.")],
					],
					tip: __("Using a ChatGPT Plus or Pro subscription instead of an API key? Open any Flow Provider and select Connect with ChatGPT. Flow creates a provider named codex after you sign in."),
				},
				{
					id: "flow-model",
					title: __("2. Add a Flow Model"),
					body: __("A model is the specific AI that agents use to think and reply. You can add several and choose one per agent or per chat."),
					doctype: "Flow Model",
					steps: [
						__("Open Flow Model and select Add Flow Model."),
						__("Enter a Title that people will recognise in the model selector, then choose the Provider you created."),
						__("Pick or type the Model ID, keep Enabled ticked, and save."),
					],
					fields: [
						[__("Title"), __("Display name shown in Chat, for example Claude Sonnet.")],
						[__("Provider"), __("The Flow Provider that holds the API key.")],
						[__("Model ID"), __("The model name, for example claude-sonnet-4-6. Flow adds the provider prefix for you.")],
						[__("Params"), __("Optional JSON such as {\"temperature\": 0.2, \"max_tokens\": 1024}.")],
					],
					tip: __("Without a Provider, write the full Model ID such as ollama/llama3.1 and fill in the model's own API Key and Base URL. Context Window is detected automatically."),
				},
				{
					id: "test-connection",
					title: __("3. Test and start chatting"),
					body: __("Confirm the connection before people start using Flow."),
					steps: [
						__("Open the Flow Model you saved and select Test Connection. If the test fails, check the API Key, Model ID, and Base URL, then save and test again."),
						__("Saving the first enabled model creates the built-in Flow assistant, the OCR agent, and the prebuilt agents for this site."),
						__("Open Flow Chat. If it still says Setup required, check that at least one model and one agent are enabled."),
					],
					note: __("Only a System Manager can add providers. Keep API keys in Flow Provider or Flow Model; never paste them into a chat."),
				},
			],
		},
		{
			id: "chat",
			title: __("Chat and agents"),
			intro: __("Ask questions, pick the right specialist, and control what each agent may do."),
			topics: [
				{
					id: "ai-chat",
					title: __("AI Chat"),
					body: __("Ask a question in normal language. Flow can find permitted information, explain it, and help complete a task."),
					example: __("Show unpaid sales invoices due this week."),
					steps: [
						__("Open Flow Chat and select New Chat. Leave the agent selector on Auto, or pick a specific agent and model."),
						__("Type your request with useful details such as the company, date range, or status. Attach files with the paperclip or by dragging them in."),
						__("Review the answer and approve or deny any action when Flow asks. Select Stop to end a reply early."),
					],
				},
				{
					id: "agent-routing",
					title: __("Automatic agent routing"),
					body: __("With Auto selected, Flow picks the best agent for each message and can switch agents during one conversation. The new agent receives a short summary of the chat so far."),
					example: __("Ask about overdue invoices, then about stock levels, in the same chat."),
					steps: [
						__("In Chat, set the agent selector to Auto before sending your first message."),
						__("Write each request normally. When Flow changes agent, the chat shows a \"Switched to\" note with the new agent."),
						__("To keep one agent for the whole chat, select that agent instead of Auto."),
					],
				},
				{
					id: "agents",
					title: __("Specialised agents"),
					body: __("Each agent has focused instructions and selected tools. Flow includes prebuilt agents for areas such as receivables, payables, bank reconciliation, inventory, GST, TDS, and payroll."),
					steps: [
						__("Open Agent from the Flow sidebar and use the Featured, Enabled, and Disabled tabs to browse agents."),
						__("A prebuilt agent is disabled when the apps or DocTypes it needs are not installed on this site."),
						__("Create your own agent by choosing a model and writing clear instructions for its role and limits."),
					],
					note: __("Auditor agents only read and report. Operator agents can also prepare draft documents for you to review."),
				},
				{
					id: "tools",
					title: __("Tools and permissions"),
					body: __("Tools let an agent read reports, find records, or make approved changes. Your Frappe permissions still apply, so Flow cannot use a tool to access a record that you cannot access."),
					steps: [
						__("Choose an agent in Chat, then select the sliders icon beside the agent selector."),
						__("Set each tool to Always Allow, Needs Approval, or Blocked."),
						__("When an approval request appears in chat, check the proposed action before approving it."),
					],
				},
			],
		},
		{
			id: "automation",
			title: __("Automation"),
			intro: __("Run agents without typing the same request every time."),
			topics: [
				{
					id: "triggers",
					title: __("Triggers"),
					body: __("A trigger starts an agent automatically when a document changes or when a schedule becomes due."),
					example: __("Review a new Lead after it is created."),
					steps: [
						__("Open Triggers from the Flow sidebar and create a Flow Trigger."),
						__("Choose an agent and either a DocType event or a scheduled cron expression."),
						__("Add an optional condition, write the prompt template, enable the trigger, and save it."),
					],
				},
				{
					id: "macros",
					title: __("Macros"),
					body: __("A macro saves one or more prompts as a reusable task. Run it again without writing the same instructions."),
					example: __("Save your weekly overdue invoice check."),
					steps: [
						__("From a useful chat, open Action and select Save as macro, or open Macro and create one."),
						__("Choose the agent, add the prompts in the order they should run, and save."),
						__("Select Run whenever needed, or enable a schedule for automatic runs."),
					],
				},
			],
		},
		{
			id: "data",
			title: __("Data, reports, and files"),
			intro: __("Answer from trusted sources, run reports, and turn files into records."),
			topics: [
				{
					id: "knowledge",
					title: __("Knowledge"),
					body: __("Knowledge gives an agent trusted reference material. This helps it answer from selected sources instead of unrelated data."),
					example: __("Answer a policy question from your company handbook."),
					steps: [
						__("Open Knowledge Base from the Flow sidebar and create a base with a clear description."),
						__("Add a Flow Knowledge Source using text, a file, a URL, or selected DocType records."),
						__("After the source status is Completed, ask an agent that has access to that knowledge base."),
					],
				},
				{
					id: "reports",
					title: __("Reports"),
					body: __("Flow can explain required report filters, run a permitted Frappe report, and summarize the result."),
					example: __("Run a sales report for the current month."),
					steps: [
						__("In Chat, choose an agent that has report tools and ask for the report by name or business purpose."),
						__("Include known filters such as company and period; Flow will ask for any required values that are missing."),
						__("Ask Flow to summarize, compare, or explain the returned results."),
					],
				},
				{
					id: "excel-export",
					title: __("Excel export"),
					body: __("Flow can put suitable table data into an Excel file. It stores the file in Frappe and returns a download link."),
					example: __("Export the invoice list to Excel."),
					steps: [
						__("Ask an agent with export access to export records or report results to Excel."),
						__("State the filters and columns you need, and approve the tool call if prompted."),
						__("When the export finishes, select the download link in Flow's reply."),
					],
				},
				{
					id: "file2erp",
					title: __("File2ERP"),
					body: __("Turn a PDF, image, spreadsheet, or document into a Frappe record. Flow reads the file, and you check the extracted fields and line items before anything is created."),
					example: __("Create a Purchase Invoice from a supplier's PDF bill."),
					steps: [
						__("Open File2ERP from the Flow sidebar and upload or drag in a file."),
						__("Choose the document type, select Extract Data, and correct any fields or line items."),
						__("Select Create to make the document, or Ask AI to continue in a chat."),
					],
				},
			],
		},
		{
			id: "history",
			title: __("History and feedback"),
			intro: __("Find earlier chats and help agents improve."),
			topics: [
				{
					id: "chat-history",
					title: __("Chat history"),
					body: __("Your recent chats appear in the Flow sidebar. Chats are deleted automatically 90 days after they start, including their messages and attached files."),
					example: __("Search the sidebar for \"overdue\" to reopen an earlier chat."),
					steps: [
						__("Use Search chats in the sidebar to find a chat by its title, then select it to continue."),
						__("Select the delete icon beside a chat to remove it immediately."),
					],
					note: __("Save anything you need to keep. Administrators can change the retention period in Log Settings."),
				},
				{
					id: "feedback",
					title: __("Feedback and memory"),
					body: __("Rate each reply so agents improve. For agents with memory enabled, a thumbs-down with a comment is saved as a lesson for future chats."),
					example: __("Thumbs down with \"Always group results by customer\"."),
					steps: [
						__("After a reply finishes, select thumbs up or thumbs down below it."),
						__("With a thumbs down, add a short comment that explains what should change."),
						__("If Flow shows Saved to agent memory, the agent will use it in later chats."),
					],
				},
			],
		},
		{
			id: "reference",
			title: __("Reference"),
			topics: [
				{
					id: "safety",
					title: __("Permissions and safety"),
					body: __("Flow uses your Frappe permissions when a tool reads or changes data. A sensitive action asks for confirmation before it continues, and agents create documents only as drafts for you to review and submit."),
				},
				{
					id: "example-prompts",
					title: __("Example prompts"),
					body: __("Select a prompt to open it in Flow Chat."),
					prompts: [
						__("Which customers have overdue invoices?"),
						__("Summarize sales for this month."),
						__("Show purchase orders waiting for delivery."),
						__("Export these results to Excel."),
					],
				},
			],
		},
	];
}

function renderHeader(page) {
	const header = $("<header>").addClass("flow-guide-header").appendTo(page);
	const brand = $("<div>").addClass("flow-guide-brand").appendTo(header);
	$(frappe.utils.icon("help", "md")).appendTo(brand);
	$("<span>").text(__("Flow Guide")).appendTo(brand);
	makeButton(header, __("Open Flow Chat"), "message-circle", () => openChat());
}

function renderIntro(article) {
	const intro = $("<header>").addClass("flow-guide-intro").attr("id", "flow-guide-top").appendTo(article);
	$("<div>").addClass("flow-guide-eyebrow").text(__("Flow documentation")).appendTo(intro);
	$("<h1>").text(__("Flow Guide")).appendTo(intro);
	$("<p>")
		.addClass("flow-guide-lead")
		.text(__("Flow is an assistant inside Frappe. It helps you ask questions, understand business information, and complete routine work in normal language instead of finding every screen or report yourself."))
		.appendTo(intro);
	$("<p>")
		.text(__("Your administrator chooses which agents, tools, and knowledge sources are available. If Flow is not set up yet, start with Set up Flow."))
		.appendTo(intro);
}

function renderChapter(article, chapter) {
	const section = $("<section>").addClass("flow-guide-chapter").attr("id", chapter.id).appendTo(article);
	const heading = $("<div>").addClass("flow-guide-chapter-head").appendTo(section);
	$("<h2>").text(chapter.title).appendTo(heading);
	if (chapter.badge) {
		const badge = $("<span>").addClass("flow-guide-badge").appendTo(heading);
		$(frappe.utils.icon("shield", "sm")).appendTo(badge);
		$("<span>").text(chapter.badge).appendTo(badge);
	}
	if (chapter.intro) $("<p>").text(chapter.intro).appendTo(section);
	chapter.topics.forEach((topic) => renderTopic(section, topic));
}

function renderTopic(section, topic) {
	const block = $("<section>").addClass("flow-guide-topic").attr("id", topic.id).appendTo(section);
	const heading = $("<div>").addClass("flow-guide-topic-head").appendTo(block);
	$("<h3>").text(topic.title).appendTo(heading);
	if (topic.doctype && frappe.user.has_role("System Manager")) {
		makeButton(heading, __("Open {0}", [__(topic.doctype)]), "external-link", () => frappe.set_route("List", topic.doctype));
	}

	$("<p>").text(topic.body).appendTo(block);
	if (topic.example) renderCallout(block, "example", __("Example"), topic.example);

	if (topic.steps) {
		$("<h4>").text(__("Steps")).appendTo(block);
		const list = $("<ol>").addClass("flow-guide-steps").appendTo(block);
		topic.steps.forEach((step) => $("<li>").text(step).appendTo(list));
	}

	if (topic.fields) renderFieldTable(block, topic.fields);
	if (topic.prompts) renderPrompts(block, topic.prompts);
	if (topic.tip) renderCallout(block, "tip", __("Tip"), topic.tip);
	if (topic.note) renderCallout(block, "note", __("Note"), topic.note);
	if (topic.action) makeButton(block, topic.action.label, topic.action.icon, topic.action.onClick, true);
}

function renderFieldTable(block, fields) {
	$("<h4>").text(__("Fields")).appendTo(block);
	const table = $("<table>").addClass("flow-guide-table").appendTo(block);
	const head = $("<tr>").appendTo($("<thead>").appendTo(table));
	$("<th>").text(__("Field")).appendTo(head);
	$("<th>").text(__("What to enter")).appendTo(head);
	const body = $("<tbody>").appendTo(table);
	fields.forEach(([label, help]) => {
		const row = $("<tr>").appendTo(body);
		$("<td>").text(label).appendTo(row);
		$("<td>").text(help).appendTo(row);
	});
}

function renderCallout(block, kind, label, text) {
	const icons = { example: "message-circle", tip: "info", note: "alert-circle" };
	const callout = $("<div>").addClass(`flow-guide-callout is-${kind}`).appendTo(block);
	$(frappe.utils.icon(icons[kind], "sm")).appendTo(callout);
	const copy = $("<div>").appendTo(callout);
	$("<strong>").text(label).appendTo(copy);
	$("<span>").text(text).appendTo(copy);
}

function renderPrompts(block, prompts) {
	const list = $("<div>").addClass("flow-guide-prompts").appendTo(block);
	prompts.forEach((prompt) => {
		const item = $("<button>").attr("type", "button").appendTo(list);
		$(frappe.utils.icon("arrow-up-right", "sm")).appendTo(item);
		$("<span>").text(prompt).appendTo(item);
		item.on("click", () => openChat(prompt));
	});
}

function renderNav(nav, chapters) {
	const details = $("<details>").addClass("flow-guide-nav-menu").attr("open", true).appendTo(nav);
	$("<summary>").text(__("Contents")).appendTo(details);
	chapters.forEach((chapter) => {
		const group = $("<div>").addClass("flow-guide-nav-group").appendTo(details);
		$("<div>").addClass("flow-guide-nav-title").text(chapter.title).appendTo(group);
		const list = $("<ul>").appendTo(group);
		chapter.topics.forEach((topic) => {
			const link = $("<a>")
				.attr({ href: `#${topic.id}`, "data-topic": topic.id })
				.text(topic.title)
				.on("click", (event) => {
					event.preventDefault();
					scrollToSection(topic.id);
				});
			$("<li>").append(link).appendTo(list);
		});
	});
	// On narrow screens the contents menu starts collapsed so the article comes first.
	if (window.matchMedia("(max-width: 1023px)").matches) details.removeAttr("open");
}

function watchActiveTopic(article, nav) {
	if (!("IntersectionObserver" in window)) return;
	const observer = new IntersectionObserver(
		(entries) => {
			const visible = entries.filter((entry) => entry.isIntersecting);
			if (!visible.length) return;
			const top = visible.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
			nav.find("a").removeClass("is-active");
			nav.find(`a[data-topic="${top.target.id}"]`).addClass("is-active");
		},
		{ rootMargin: "-72px 0px -60% 0px" }
	);
	article.find(".flow-guide-topic").each(function () {
		observer.observe(this);
	});
}

function scrollToSection(id) {
	document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
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
