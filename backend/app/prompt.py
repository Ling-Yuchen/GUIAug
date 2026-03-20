operation_desc_generate_prompt = """
You are an expert in GUI test script interpretation for mobile apps.
Each test step consists of:
- screenshot: a screenshot of the screen before the operation
- target_widget: a cropped image of the UI widget being interacted with

Your task is to generate a clear and concise natural language description for the current step based on the images provided to you.

For example:
- tap the heart button in the top navigation bar
- tap the settings icon in the page right upper corner
- tap the profile picture in the page body, row 2 column 1
- tap the "Submit" button in the dialog box, bottom area
- tap the "work", the second option in the dropdown list
- tap the "Next" button in the page footer

Note that: a simple description of the widget and its position should be included

Return your response in JSON format: {result: "..."}
""".strip()

operation_intent_generate_prompt = """
You are an expert in GUI test script interpretation for mobile apps.
Each test step consists of:
- operation_type: the kind of user action
- screenshot: a screenshot of the screen before the operation
- target_widget: a cropped image of the UI widget being interacted with (optional)
- input_text: specific input text to enter (optional)

Given the following context:
- Previous steps: {PREVIOUS-OPERATIONS}
- Current step metadata:
  - operation_type: {OPERATION-TYPE}
  - input_text: {INPUT-TEXT}
  - screenshot: <see image(s) attached>
  - target_widget(optional): <see image(s) attached>

Your task is to generate a clear and concise natural language description for the current step and its intent.

For example:
- tap the heart button in the top navigation bar to favorite the article
- tap the settings icon in the page right upper corner to open configuration options
- tap the profile picture in the page body, row 2 column 1 to view user details
- tap the "Submit" button in the dialog box, bottom area to confirm the action
- tap the "work", the second option in the dropdown list to select a tag
- tap the "Next" button in the page footer to go to the following step
- scroll the left area of screen to find out more options
- enter "pizza hut" to search for food delivery information

Note that:
1. For *tap* and *long_press* operation, a simple description of the widget and its position should be included)
2. For *input* and *assert* operation, the specific text for input or assertion must be included

Return your response in JSON format: {result: "..."}
""".strip()

script_intent_generate_prompt = """
You are an expert in summarizing mobile GUI test scripts.

Given the following list of step-level intents describing a test script:

{OPERATION-INTENTS}

Generate a concise and coherent natural language summary that explains what this test script does as a whole.
Focus on the user goal or the test purpose. Keep the tone formal and task-oriented.

Return your response in JSON format: {result: "... (be brief and abstract)"}
""".strip()

input_type_query_prompt = """
You are an assistant analyzing GUI test scripts for mobile apps.
Each step in the script describes a user action in natural language.

You are given:
- The full test script (as context)
- A specific input step to analyze

Your task is to determine whether the specified input step is:
- **content-oriented**: The input is arbitrary text used only for display or filler. It has no impact on business logic.
- **business-oriented**: The input must meet certain rules, formats, or business constraints. It is necessary for functional correctness or affects app logic.

INSTRUCTIONS:
1. Read the full script to understand the context.
2. Focus on the specified input step.
3. Decide if the input is "content-oriented" or "business-oriented".
4. Provide your reasoning.
5. If the input is business-oriented, also specify the **requirement** — what conditions, format, or logic the input must satisfy.
6. Output your result in **JSON format** as shown below.
---
{"type": "content-oriented" | "business-oriented", "reason": "your explanation here", "requirement": "(OPTIONAL)"}
---

EXAMPLES:

Input:
1. clicks the comment button  
2. types "Nice work!" into the comment field ← (input to analyze)
3. clicks the submit button

Output:
{
  "type": "content-oriented",
  "reason": "The input is a free-form user comment that can be arbitrary. Any text is acceptable."
}

---

Input:
1. clicks the search button  
2. enters "Taylor Swift" into the search input field ← (input to analyze)
3. clicks the first recommended option

Output:
{
  "type": "business-oriented",
  "reason": "The input is used to search for real songs or artists. It must correspond to valid entities in the music database to return relevant results.",
  "requirement": "matching a valid artist name or song title in the music library"
}

---

Now analyze the following case:

Full test script:
{FULL-TEST-SCRIPT}

Input step to analyze:
{SPECIFIC-INPUT-STEP-DESCRIPTION}

Please return your result in JSON format only.
""".strip()

content_input_mutate_query_prompt = """
You are given an input operation from a GUI test script, classified as "content-oriented".
This means the input value is arbitrary and only used for display or filler purposes, not affecting the app's business logic.

Your task is to generate mutated versions of the original input based on the following mutation directions and quantities:
- Length variation: generate {NUM_LENGTH} mutations (e.g., very long)
- Language variation: generate {NUM_LANGUAGE} mutations (e.g., translate or rewrite into different languages)
- Character variation: generate {NUM_CHAR} mutations (e.g., add emojis, special characters, numbers)

For each mutated input, return:
- The new input string
- A short explanation of what was changed

Return your output in this JSON format:
{
  "original_input": "...",
  "mutations": [
    {
      "value": "<new string for input only, no extra information>",
      "type": "length"|"language"|"character",
      "reason": "..."
    }
  ]
}

---

Now mutate the following input operation:
{INPUT-OPERATION-FOR-MUTATION}
""".strip()

business_input_mutate_query_prompt = """
You are given an input operation from a GUI test script, classified as "business-oriented".
This means the input should meet a specific rule to function correctly in the application.

Your task is to generate mutated versions of the original input based on the following mutation directions and quantities:
- Rule-based variation: generate {NUM_VALID} mutations that satisfy the specific rule
- Rule-violated variation: generate {NUM_INVALID} mutations that violate the rule in different ways

For each mutated input, return:
- The new input string
- Whether it is valid (`true`) or invalid (`false`)
- A brief explanation of what was changed and why

Return your result in the following JSON format:
{
  "original_input": "...",
  "rule": "...",
  "mutations": [
    {
      "value": "<new input string only, no extra information>",
      "valid": true | false,
      "reason": "..."
    }
  ]
}

---

Now perform the mutation.

Input operation: {INPUT-OPERATION-FOR-MUTATION}  
Specific rule: {BUSINESS-RULE-DESCRIPTION}
""".strip()

option_data_mutate_query_prompt = """
You are a mobile GUI testing assistant specialized in performing *Option Mutation* on GUI test scripts using only visual information from the UI screenshot.

Option Mutation means replacing a user action that selects one option from a group of alternatives (e.g., a radio button or dropdown menu item) with a different valid option in the same group, without breaking the logical flow of the app.

You are provided with:
- A screenshot of the UI before the operation, with each UI widget annotated by a bounding box and a unique index number.
- A natural language description of the target operation: {TARGET-OPERATION}

Your task is to:
1. identify the UI widget involved in the **target operation**
2. locate alternative options of the identified UI widget from the same logical group
3. return alternative options as mutation candidates

Return all the alternative options (excluding the original one) as a list of their index.
Please return your answer in the following JSON format:
{
  "mutated_options": [
    {
      "alternative_widget_index": "<index of UI element>",
      "reason": "<brief explanation of why this option is a valid alternative>"
    },
    ...
  ]
}
""".strip()

widget_rank_for_mutation_query_prompt = """
You are a GUI widget ranker.
A screenshot is provided where AVAILABLE CANDIDATES are visually marked with bounding boxes and readable IDs.
Rank ONLY these labeled boxes.

Primary objective: advance the test goal of the target scenario.
Secondary factors: reachability/visibility, stability (clear affordance), oracle-check potential, time/cost.
Avoid hard constraints (e.g., payment or destructive actions) inferred from visible text/icons.

Test Goal: {TEST_GOAL}

Rules:
- Consider ONLY boxes with a readable ID in the image. Ignore unlabeled areas.
- If an element looks like a text field, "input" is allowed; otherwise default to "tap".
- Mark risk tags if text suggests payment/destructive action (e.g., "Pay", "Delete", "Reset").

Output strictly as JSON:
{
  "rank_list": [
    { "bbox_id": "<ID as seen in the image>", "op_type": "tap|input", "score": 0.0, "tags": ["<short reason>", "risk(optional)"] },
    ...
  ]
}
Notes:
- score in [0,1]; break ties by bbox_id ascending.
- return at most 20 IDs in the screenshot image.
""".strip()

path_mutate_query_prompt = """
You are a test agent performing path mutation for GUI testing.

You are tasked with incrementally exploring a new interaction path for testing, starting from a specific mutation point in the original script. 
Each subsequent action should build upon the mutated path created from the previous steps.

---

## Mutation Test Goal:
{TEST_GOAL}

---

## Original Test Script:
(This is for context only. Do not simply reuse this sequence. It provides the original steps for reference.)
{ORIGINAL_SCRIPT}

---

## Actions Taken So Far:
{MUTATED_STEPS}

(This is the unfinished mutating script, i.e., a new evolving test path.)

---

## Current Screen:
A screenshot of the app's current state is attached.  
All available candidate UI widgets are labeled with bounding boxes and indexes in this screenshot.

---

## Your Task:
Propose the next most appropriate action to move toward the mutation test goal.

Warning:
1. Do not reuse the original script's actions unless they are clearly required by this new path.
2. When an attempt has been repeated in "Actions Taken So Far", reflect on the current screen and choose a rational adjustment.

---

## Response format:
Please return your answer in the following JSON format:
{
  "reasoning": "<brief explanation of your action choice>",
  "next_action": {
    "type": "tap" | "input" | "long_press" | "back",
    "target": <an existing integer widget index in the screenshot> | null,
    "text": "<text for input action>" | null,
    "description": "<brief description of your next action>"
  }
}
""".strip()

widget_semantic_match_prompt = """
## TASK
You are replaying an automated GUI test.
Your goal is to match the natural language description of the original operation to exactly one widget from the current target screenshot.

## INPUTS
- Operation description: a short natural language statement describing the target widget and its approximate position.
- Target screenshot: all candidate widgets are detected, each enclosed by a green bounding box and labeled 0..N.

## RULES
1. Exact match priority
    - If a candidate clearly and fully matches the description (same control type, label, or icon), you must select it.
    - Do not ignore or downgrade a perfect match.
2. Fallback for page changes
    - If no candidate exactly fits, choose the widget that best serves the same role/purpose and is plausibly in the same area or grouping described.
    - It may be a replacement, a container, or a dominant element in that slot with different contents.
3. Sanity checks
    - The chosen candidate’s visible properties (icon, text, control type, approximate location) must align with the description or its intended purpose.
    - Do not invent attributes that are not visible.
    - Avoid picking something obviously unrelated (e.g., text paragraph instead of an icon, decorative graphic instead of a button).
4. Returning -1
    - Only return -1 if no candidate plausibly corresponds to the description, even considering replacements or role-based alternatives, or if the screenshot is unreadable.
    - This decision must be very cautious.

## OUTPUT
Return JSON only:
{
  "match_number": <int>,    // 0..N, or -1 if no suitable match
  "reason": "<short explanation of why this candidate was chosen or why -1>"
}
""".strip()

oracle_text_match_prompt = """
You are an AI agent tasked with verifying if any part of the extracted text from a screenshot is semantically similar to a given target text.

## Inputs
1. Extracted text from the current screenshot (contains many text segments): ```{EXTRACTED_TEXT}```
2. Target text to compare with: ```{TARGET_TEXT}```

## Task
- Check if any part of the extracted text semantically matches the meaning of the target text.
- The extracted text may consist of multiple sentences or fragments; you need to search through all the extracted text to find any segments that convey a meaning similar to the target text.
- If you find a semantically similar match, return `{"result": true, "reason": "<brief explanation>"}`.
- If no semantically similar match is found, return `{"result": false, "reason": "<brief explanation>"}`.

## Instructions
- Focus on the overall meaning of the segments, not just exact word matching.
- The reason should explain why a certain segment is considered semantically similar or not.
- If no match is found, clearly explain that no semantically similar content was found in the extracted text.
- If a match is found, summarize how that part of the extracted text conveys a meaning close to the target text.
- Return the JSON object only, no extra output.

## Example 1
Extracted Text: ```share with; playback settings; Check out the new updates; Operation completed successfully; Scheduled shutdown```
Target Text: ```Song added successfully```
Output: { "result": true, "reason": "The segment 'Operation completed successfully' conveys a similar meaning to 'Song added successfully.' Both express a successful action completion." }

## Example 2
Extracted Text: ```Welcome to the music app; Try again later; Check out our new features; Sign up to get started```
Target Text: ```Song added successfully```
Output: { "result": false, "reason": "None of the extracted segments express that the song has been successfully added to the playlist." }
""".strip()

semantic_assertion_prompt = """
## Role
You are a meticulous GUI test oracle. Your job is to judge whether a natural-language assertion about a user interface is true or false based solely on a single screenshot of the current screen.

## Objective
Given a natural-language assertion about the UI state or content, and a screenshot image of the current page, determine if the assertion is satisfied by the screenshot evidence. Return a strict JSON object with your decision and a brief justification.

## Inputs
Assertion: `{ASSERTION_TEXT}`
Screenshot: (see the uploaded image)
Note: The screenshot is the only visual evidence available. Assume no hidden interactions or dynamic states beyond what is visible.

## Evaluation Procedure and Criteria
Follow these integrated steps and rules carefully to make a precise, evidence-based judgment:
  1. Understand the Assertion: Break down the natural-language assertion into clear, checkable visual conditions (e.g., “text presence,” “element visible,” “sorted list”).
  2. Inspect the Screenshot: Examine the visible UI elements, texts, icons, colors, and layout. Use OCR-like reasoning to read visible texts and numeric values.
  3. Verify Conditions: Check the relevant aspects based on the assertion type, such as,
    a. Presence/absence: Messages, dialogs, buttons, error banners.
    b. Text content: Keywords or equivalent phrases (e.g., “Login successful” ≈ “Signed in successfully”).
    c. Sorting/ordering: Lists ordered by price, time, name, etc.
    d. Counts/uniqueness: Expected number of visible items or no duplicates.
    e. State/visibility: Enabled/disabled, selected/unselected, visible/hidden (if clearly observable).
    f. Layout/position: Relative order or grouping on screen.
  4. Decision Logic: Conclude true only if the screenshot provides clear evidence supporting the entire assertion. If any required element is missing, unreadable, ambiguous, or partially visible, output false. Do not speculate about off-screen or hidden content. Prefer exact or semantically equivalent matches. When uncertain, choose false and briefly explain the uncertainty.
  5. Summarize Judgment: Generate a concise, factual reason referencing visible evidence or missing elements. The explanation should be ≤200 characters.

## Output Format
Return a JSON object: {"assertion_pass": true|false, "reason": "<brief explanation of the judgment>"}

## Examples
Assertion: `A success message indicating a successful login appears on the screen.`
Screenshot: visible toast says "登录成功" in the screenshot image.
Expected Output: {"assertion_pass": true, "reason": "Found visible success message '登录成功' near top of screen."}

Assertion: `All products are sorted by price from highest to lowest.`
Screenshot: prices appear ¥999, ¥499, ¥699, ¥399, ¥199.
Expected Output: {"assertion_pass": false, "reason": "Price order incorrect or partially unreadable."}
""".strip()

input_assert_binding_prompt = """
## Role
You are an expert in GUI testing analysis and software behavior reasoning.

## Objective
Given a GUI test script described in natural language and a specific input operation in it, identify assertion operations within the GUI test script that are logically or causally bound to the specified input operation.
A bound assertion is one whose verification content would change if the input value or content were changed.
Return a structured JSON list showing, for each assertion, its operation index, the confidence of being bound to the specified input operation, and a concise reasoning statement.

## Inputs
Full GUI Test Script:
{SCRIPT_OPERATIONS}
Specified Input Operation: `{INPUT_INTENT}` ({INPUT_TYPE_DESC})

## Evaluation Procedure and Criteria
1. Dependency Analysis: Identify whether each assertion’s verification target depends on or reflects the data affected by the given input operation.
2. Causality Assessment: Determine if the assertion verifies a result, message, or displayed value that would vary when the input changes. If yes, consider it bound to that input.
3. Confidence Scoring: Assign a numeric confidence score in the range 0.0–1.0, where 1.0 → Strongly bound (direct dependency), 0.5 → Possibly bound (partial or indirect relationship), 0.0 → Unrelated (no dependency).
4. Rationale Requirement: For each assertion, provide a short, factual explanation describing the reasoning for the confidence score.

## Output Format
Return a JSON object with the following schema:
{
  "result": [
    {
      "assertion_index": "<operation index of the assertion>",
      "binding_confidence": <float between 0 and 1>,
      "rationale": "<brief reasoning explaining the dependency or lack thereof>"
    },
    ...
  ]
}

## Example
Full GUI Test Script:
  [1] Open the product search page.  
  [2] Enter "wireless mouse" into the search bar to find related products.  
  [3] Click the "Search" button to execute the query.  
  [4] Assert that the search results list contains items related to "wireless mouse".  
  [5] Assert that the page title changes to "Search Results".  
  [6] Assert that the "No results found" message is not displayed.
Specified Input Operation: "Enter "wireless mouse" into the search bar to find related products." (content-oriented input without input rule)
Expected Output:
{
  "result": [
    {
      "assertion_index": "4",
      "binding_confidence": 0.95,
      "rationale": "The search results directly depend on the input text value."
    },
    {
      "assertion_index": "5",
      "binding_confidence": 0.3,
      "rationale": "The page title changes after performing a search but is not specific to the input text."
    },
    {
      "assertion_index": "6",
      "binding_confidence": 0.8,
      "rationale": "The presence or absence of the 'No results found' message depends on the query input."
    }
  ]
}
""".strip()

new_assertion_generate_prompt = """
## Role
You are a meticulous GUI test-engineering assistant.
You are good at modifying GUI test scripts based on detailed contexts.

## Objective
Given:
- a full GUI test script described step-by-step in natural language,
- a specific input step that has been changed (including the new text value),
- a target assertion step from the script, and the rationale describing why that input step and assertion are bound (i.e., how the input influences the assertion),
rewrite the assertion so it is consistent with the modified input while preserving the test’s intent and level of specificity.
If the change does not affect the assertion according to the binding rationale, return the original assertion verbatim.

## Inputs
Full GUI Test Script:
{SCRIPT_OPERATIONS}
Modified Input Operation: `{INPUT_INTENT}` → the input content has been modified to "{NEW_INPUT_TEXT}"  ({MUTATION_DESCRIPTION})
Target Assertion: `{ASSERTION_DESC}`
Binding Rationale: `{BINDING_REASON}`

## Evaluation Procedure and Criteria
When producing the updated assertion, follow these rules:
  1. Stay Within Script Context: Ensure the updated assertion refers only to UI elements and states that exist in the script.
  2. Reflect the New Value Exactly: Substitute literals (e.g., titles, labels) with the new value precisely, including case and punctuation.
  3. Preserve Intent & Granularity: Maintain the same assertion type and specificity, unless the binding rationale requires a change.
  4. Business-oriented Input Rule Violations: If the input change violates a business rule, adjust the assertion accordingly based on the specific context.
  5. Clarity & Testability: The assertion must remain clear, concise, and easily verifiable.
  6. No Overreach: Avoid adding unrelated changes unless explicitly supported by the rationale.
  7. Language & Style Consistency: Keep the language and style consistent with the original assertion.

## Output Format
Return a JSON object: {"new_assertion": "<the updated assertion sentence>"}

## Examples
Full GUI Test Script:
  [1] Open the homepage.
  [2] Type “laptop” into the search box.
  [3] Click the “Search” button.
  [4] Assert that the results header shows “Results for laptop”.
Modified Input Operation: `Type “laptop” into the search box.` → the input content has been modified to "smartphone"
Target Assertion: `The results header shows “Results for laptop”.`
Binding Rationale: `The results header echoes the user’s query string.`
Expected Output: {"new_assertion": "The results header shows 'Results for smartphone'"}

Full GUI Test Script:
  [1] Open the login page.
  [2] Type “user@163.com” into the email field.
  [3] Click the “Login” button.
  [4] Assert that the results header shows “Welcome, user@163.com”.
Modified Input Operation: `Type “user@163.com” into the email field.` → the input content has been modified to "12345abcde"
Target Assertion: `Assert that the results header shows “Welcome, user@163.com”.`
Binding Rationale: `changing the input email would change the expected login state`
Expected Output: {"new_assertion": "the page either shows an invalid email format error, fails to log in, or does nothing"}
""".strip()

input_assert_binding_detect_prompt = """
You are given a test script (as a list of operation descriptions) and ONE specific input operation that will be mutated.
Your task is to discover which assert operations are semantically bound to this input, and to output a binding plan.

### Input Operation (the only one you should bind)
- input_type: "{INPUT_TYPE}"
- input_intent: "{INPUT_INTENT}"

### Script Operations
{SCRIPT_OPERATIONS}

### Policies to use
- "ECHO_INPUT": the assert should echo the mutated input value exactly as the expected text.
- "TEMPLATE_WITH_INPUT": the assert should use a template that MUST contain the literal placeholder "{input}".
- "SUCCESS_ON_VALID_ELSE_ERROR": for business rules, use "success_text" when the input is valid; otherwise use "error_text".

### Decision rules
1) For content-oriented inputs:
   - Typically use "ECHO_INPUT". If echoing is unlikely, use "TEMPLATE_WITH_INPUT" and provide "template" (must contain "{input}").
   - Do NOT use "SUCCESS_ON_VALID_ELSE_ERROR" unless there is explicit, strong evidence of success/error messaging tied to this input (rare for content-oriented).

2) For business-oriented inputs:
   - Consider ALL policies. Select the one(s) best supported by the script evidence.
   - Use "SUCCESS_ON_VALID_ELSE_ERROR" **only if** the script indicates distinct success/error outcomes for this input (e.g., assert intents or texts contain tokens like “成功”, “失败”, “错误”, “登录成功”, “密码错误”, or refer to toast/alert/error messages).
   - Use "ECHO_INPUT" or "TEMPLATE_WITH_INPUT" if the bound asserts appear to display or incorporate the input value itself (e.g., search results echoing the query).
   - If multiple asserts exist, you may bind different asserts with different policies (e.g., one echo, one success/error).

3) Evidence and text sourcing:
   - Prefer reusing/aligning with existing assert texts from the script (language, tone, terminology).
   - If introducing new messages (only when necessary), keep them brief, plausible, and consistent with the script language.
   - Avoid inventing highly specific messages without support; lower confidence when evidence is weak.

4) Output scope:
   - Only bind asserts that actually exist in the provided script.
   - Return at most **one** binding object for the given input_op_id, with zero or more assert bindings inside.

5) JSON quality:
   - Output **valid JSON only** (double quotes, no comments, no trailing commas). No extra prose.
   - "confidence" MUST be a number in [0, 1].

### Output format (JSON ONLY)
{
  "bindings": [
    {
      "assert_op_idx": "<must be an index of an assert operation from the script>",
      "policy": "ECHO_INPUT" | "TEMPLATE_WITH_INPUT" | "SUCCESS_ON_VALID_ELSE_ERROR",
      "template": "<required iff policy == 'TEMPLATE_WITH_INPUT' and MUST contain '{input}'>",
      "success_text": "<required iff policy == 'SUCCESS_ON_VALID_ELSE_ERROR'>",
      "error_text": "<required iff policy == 'SUCCESS_ON_VALID_ELSE_ERROR'>",
      "confidence": float,
    }
  ]
}
If there is no valid binding, return:
{"bindings": []}
""".strip()

mutation_point_candidate_filter_prompt = """
## Role
You are a senior mobile QA engineer specializing in mutation-based GUI test generation.
Your task is to evaluate the Branching Value (Mutation Gain) of a candidate operation as a mutation point.

## Objective
Assess not only how many alternative paths could branch from the current app state (branching potential),
but also how valuable those branches are — in terms of functional diversity, coverage gain, and expected usefulness for generating differentiated test scripts.

## Inputs
Full GUI Test Script:
{SCRIPT_OPERATIONS}
Candidate Operation: {CANDIDATE_OPERATION}
Widget Screenshot: Image of the UI widget targeted by the candidate operation. (see the uploaded images)
App Screenshot: Image of the app screen right before the candidate operation executes. (see the uploaded images)

## Evaluation Procedure and Criteria
1. Locate Context: Identify preserved prefix steps, i.e., all the steps before the candidate operation within the Full GUI Test Script.
2. Screen State Inference: From the App Screenshot (and the preserved prefix steps), summarize the current screen (app state).
3. Assess Branching Potential (Opportunity)
  - Hubness: Is this screen a hub (many navigable options) or a tail (single path)?
  - Alternative Actions Count: Approximate number of distinct visible actions.
4. Assess Branching Value (Gain)
  - Functional Diversity: Do the possible branches lead to meaningfully different goals or functions?
  - Coverage Gain: Would branching here cover new app features or workflows not seen elsewhere in the script?
  - Generative Benefit: Would this mutation point yield distinct and test-worthy new scripts (not trivial UI variants)?
5. Score Branching Value (0–5)
  - 5 = many and diverse meaningful branches, strong coverage gain
  - 4 = several distinct and useful branches
  - 3 = some variation, moderate gain
  - 2 = limited difference or small coverage increase
  - 1 = nearly redundant branches
  - 0 = no real branching value

## Output Format
Return a JSON object:
{
  "state_inference": "<brief summary of the app screen (app state)>",
  "branching_value_score": <int, 0-5>,
  "reason": "<brief explanation of the judgment>"
}
""".strip()

mutation_goal_decide_prompt = """
## Role
You are an expert in test script generation, with a deep understanding of application testing and GUI scripting.
Your task is to assist in creating a clear, specific, and actionable goal for a newly generated test script based on an existing script.

## Objective
Given a GUI script for an app, your job is to define a concise and precise goal for a new test script.
The new script will extend the existing one by introducing new, different functional scenarios.
Your goal should ensure that the new test script will cover a different aspect of the application's functionality from the original one.

## Inputs
App Type: {APP_TYPE}
Original Test Script:
{SCRIPT_OPERATIONS}
Retained Part of Original Test Script:
{RETAINED_OPERATIONS}
Current Screen Screenshot (after retained operations): (see the uploaded image)
The screenshot will give context on the current state of the app after the retained actions, which will be useful to define the new goal for the test script.

## Output Format
Return a JSON object containing the following fields:
{
  "goal": "<A concise and specific goal statement describing the expected target of the new test script>",
  "reason": "<Explanation of how this goal relates to the retained operations and the current screen state after these operations>"
}

## Example
App Type: Email
Original Test Script:
  [1] tap the menu icon
  [2] tap "Sent Mails"
  [3] tap "Search for Mails"
  [4] enter "meeting"
  [5] tap the first item in the search results
Retained Part of Original Test Script:
  [1] tap the menu icon
Current Screen Screenshot: A side menu containing various sections like "Sent Mail", "Spam", "Starred", etc.
Expected Output:
{
  "goal": "navigating to the 'Spam' folder and marking an email as 'Not Spam'",
  "reason": "The new test script will continue from the retained menu tap action, ensuring that the 'Spam' folder navigation and the email management process are tested, involving multiple steps that are different from the original search functionality."
}
""".strip()

assertion_injection_locating_prompt = """
## Role
You are a test automation assistant. Your task is to decide where to insert a critical assertion in a GUI test script.

## Objective
Given the complete sequence of operations in the GUI test script, determine the position between two operations where an assertion should be inserted.
The assertion should validate a visually-perceptible condition based on the app's state after a particular operation is completed.
The assertion should be inserted between two operations (or after the last operation).
Consider only the most critical assertion potential.

## Inputs
Full GUI Test Script:
{SCRIPT_OPERATIONS}

## Evaluation Procedure and Criteria
1. Review the description of operations to identify or infer significant app state transitions.
2. Based on the review result, reason and select the most appropriate location for assertion injection.

## Output Format
Return a JSON object:
{
  "assertion_insertion_point": {
    "after_operation": <int>,
    "before_operation": <int|null>
  },
  "reason": "<brief explanation of the decision>"
}

## Example
Full GUI Test Script:
  [1] Enter "admin" in the username field
  [2] Enter "123456" in the password field
  [3] Tap the "Login" button
Expected Output:
{
  "assertion_insertion_point": {
    "before_operation": null,
    "after_operation": 3
  },
  "reason": "After tapping the 'Login' button, it's necessary to verify if the login was successful."
}
""".strip()

assertion_injection_generating_prompt = """
## Role
You are a GUI test script developer. Your task is to write an assertion in natural language.

## Objective
Generate an assertion, i.e., a natural language description of a visual condition that should be validated based on the provided context.
The description should focus on observable elements, such as button states, text changes, or element visibility.

## Inputs
Operation Description: {OPERATION_DESCRIPTION}
Post-execution Screenshot: (see the uploaded image)

## Output Format
Return a JSON object:
{"assertion_content": "<brief description of assertion content>"}

## Example
Operation Description: Tap the "submit" button to login
Post-execution Screenshot: (a screenshot of the homepage showing a welcome message with the user's name in the top right corner)
Expected Output: {"assertion_content": "the interface contains a welcome message with the user's name in the top right corner"}
""".strip()

mutation_ending_check_prompt = """
## Role
You are an expert GUI test script developer. Your task is to decide whether a GUI test script has fulfilled the expected goal.

## Objective
Determine if the given GUI test script achieves the expected functional goal based on both the logical sequence of operations and the resulting user interface shown in the latest screenshot.
You must reason step-by-step, but output only the final structured JSON result.

## Inputs
Expected Goal: {TEST_GOAL}
GUI Test Script:
{MUTATED_STEPS}
Latest Screenshot: (see the uploaded image)

## Evaluation Procedure and Criteria
Follow these reasoning and evaluation steps:
1. Comprehension Phase: Understand what the expected goal requires functionally and visually. Identify the key conditions or indicators of goal achievement (UI state, element presence, text value, navigation status, etc.).
2. Script Analysis Phase: Analyze the given script to infer what actions the script performs and in what order. Determine if these actions logically lead to achieving the goal.
3. Screenshot Verification Phase: Examine the Latest Screenshot for evidence confirming that the expected result is visually or functionally present.
4. Decision Phase: Conclude whether the script fully or partially meets the expected goal. Justify your reasoning concisely.

## Output Format
Return a JSON object:
{
  "goal_understanding": "<concise explanation of what the expected goal requires>",
  "script_analysis": "<summary of the behavior and intention of the current script>",
  "screenshot_analysis": "<what is visible or missing in Latest Screenshot relevant to the goal>",
  "judgement": "success" | "partial",
  "reason": "<concise reasoning that justifies the final judgement>",
}

## Example
Expected Goal: uploading and saving a profile picture
GUI Test Script:
  [1] Click 'Home' icon
  [2] Click 'Edit Profile' button
  [3] Click 'Upload Picture' button
  [4] Select file 'avatar.png'
  [5] Click 'Save' button
Latest Screenshot: The UI shows the Edit Profile page with the selected file name 'avatar.png' displayed, but the profile has not been saved.
Expected Output:
{
  "goal_understanding": "The goal requires uploading a new profile picture, saving the profile, and verifying that the updated picture appears on the profile summary page.",
  "script_analysis": "The script navigates to the profile editor and selects an image file, but it never saves the changes because the 'Save' action is missing.",
  "screenshot_analysis": "The screenshot shows the selected file 'avatar.png' in the edit form, but no indication of the profile being saved or the updated picture appearing in any preview or summary section.",
  "judgement": "partial",
  "reason": "The script partially completes the goal by selecting an image, but the lack of a save action prevents the profile picture from being applied or displayed. The goal cannot be fully achieved without committing the change."
}
""".strip()