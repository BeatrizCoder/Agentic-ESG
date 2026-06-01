# Frontend/User Journey Document: Multi-Agent Customer Support Crew MVP

## User Journey Overview

The Multi-Agent Customer Support Crew MVP provides a simple, transparent interface for users to submit customer support inquiries and observe how multiple AI agents collaborate to provide responses. The primary interface is a command-line application that demonstrates the multi-agent workflow, with an optional simple web interface using Streamlit for broader accessibility.

The journey emphasizes clarity, trust, and observability - users can see exactly what each agent is doing, why decisions are made, and when human intervention might be needed. This transparency builds confidence in the AI system while educating users about multi-agent collaboration.

## Main User Goal

**Primary Goal**: Submit a customer support inquiry and receive a helpful, contextually appropriate response while understanding how the AI system arrived at that answer.

**Secondary Goals**:
- Observe the multi-agent decision-making process
- Understand when and why escalation to human agents occurs
- Feel confident in the system's capabilities and limitations
- Easily retry or modify inquiries for better results

## Step-by-Step Flow from Ticket Input to Final Response

### Step 1: Inquiry Submission
**User Action**: User enters their customer support question or issue via CLI input or text area.

**What User Sees**:
```
Multi-Agent Customer Support Crew v1.0
========================================

Enter your customer support inquiry:
> My order #12345 hasn't arrived yet. Can you help?

[Submit] [Clear] [Exit]
```

**System Behavior**: Input is captured and validated for basic requirements (non-empty, reasonable length).

### Step 2: Agent Processing Initiation
**User Action**: Clicks submit or presses enter.

**What User Sees**:
```
Processing your inquiry...
========================================

🤖 Starting Multi-Agent Analysis...

Agent 1/5: Classifier Agent 🔍
Status: Analyzing request category...
```

**System Behavior**: Orchestrator begins sequential agent execution, showing progress.

### Step 3: Classifier Agent Activity
**What User Sees**:
```
Agent 1/5: Classifier Agent 🔍
Status: Analyzing request category...
✅ Completed: Category detected - "Order Issues"
Confidence: High (85%)

Agent 2/5: Sentiment Analysis Agent 💭
Status: Evaluating emotional tone...
```

**Agent Activity Visibility**:
- Shows agent name and emoji
- Displays current task
- Indicates completion with checkmark
- Shows result and confidence level

### Step 4: Sentiment Analysis Agent Activity
**What User Sees**:
```
Agent 2/5: Sentiment Analysis Agent 💭
Status: Evaluating emotional tone...
✅ Completed: Sentiment - "Concerned"
Urgency: Medium

Agent 3/5: Knowledge Retrieval Agent 📚
Status: Searching knowledge base...
```

**Trust Elements**:
- Transparent sentiment detection helps users understand how their tone affects response
- Urgency level explains prioritization logic

### Step 5: Knowledge Retrieval Agent Activity
**What User Sees**:
```
Agent 3/5: Knowledge Retrieval Agent 📚
Status: Searching knowledge base...
✅ Completed: Found 2 relevant articles
- "Order Delivery Delays"
- "Tracking Your Package"

Agent 4/5: Response Generation Agent ✍️
Status: Crafting response...
```

**Transparency Elements**:
- Shows number of relevant articles found
- Lists article titles for context
- Indicates when no relevant knowledge is found

### Step 6: Response Generation Agent Activity
**What User Sees**:
```
Agent 4/5: Response Generation Agent ✍️
Status: Crafting response...
✅ Completed: Response generated
Confidence: Medium (72%)

Agent 5/5: Escalation Agent 🚨
Status: Evaluating escalation needs...
```

**Observable Process**:
- Shows response generation progress
- Displays confidence score for transparency

### Step 7: Escalation Agent Activity
**What User Sees** (No Escalation Case):
```
Agent 5/5: Escalation Agent 🚨
Status: Evaluating escalation needs...
✅ Completed: No escalation needed
Reason: Sufficient confidence in automated response

========================================
📋 FINAL RESPONSE
========================================

I'm sorry to hear about the delay with your order #12345. Based on our records, your package is experiencing a slight delay due to weather conditions. You should receive it within the next 2-3 business days.

For real-time tracking, please visit our website and enter your order number.

If you need immediate assistance, please call our support line at 1-800-HELP-NOW.

Thank you for your patience!

[👍 Helpful] [👎 Not Helpful] [🔄 Retry] [📞 Escalate Manually] [❌ New Inquiry]
```

**What User Sees** (Escalation Case):
```
Agent 5/5: Escalation Agent 🚨
Status: Evaluating escalation needs...
⚠️  ESCALATION TRIGGERED
Reason: Low confidence in response (45%)

========================================
🚨 HUMAN ESCALATION REQUIRED
========================================

Your inquiry has been flagged for human review due to its complexity. A support agent will contact you within 24 hours.

Reference ID: ESC-2026-0426-001

For immediate assistance, please call 1-800-HELP-NOW.

[📞 Call Now] [📧 Email Update] [❌ New Inquiry]
```

## How Agent Activity is Made Observable

### Progress Indicators
- **Sequential Progress Bar**: Shows current agent (1/5, 2/5, etc.)
- **Status Messages**: Real-time updates on what each agent is doing
- **Completion Checkmarks**: Visual confirmation when each agent finishes
- **Confidence Scores**: Numerical indicators of agent certainty

### Transparency Features
- **Agent Names and Roles**: Clear labels for each agent's specialty
- **Process Descriptions**: Plain language explanations of what each agent does
- **Result Summaries**: Brief explanations of outcomes
- **Reason Codes**: Why certain decisions were made (escalation reasons, confidence levels)

### Visual Design Elements
- **Emojis**: Friendly visual identifiers for each agent type
- **Color Coding**: Green for success, yellow for warnings, red for escalations
- **Structured Layout**: Clear sections separating different phases
- **Action Buttons**: Prominent options for user interaction

## Trust and Transparency Elements

### Confidence Indicators
- Every agent output includes a confidence score
- Low confidence triggers escalation or warnings
- Users understand when AI is uncertain

### Process Visibility
- Users see the "thinking process" of each agent
- No black-box decision making
- Clear reasoning for escalations

### Educational Elements
- Agent roles are explained through interface
- Users learn about multi-agent collaboration
- Transparency builds understanding and trust

### Safety Measures
- Clear escalation paths when AI is unsure
- Multiple contact options for human support
- Feedback mechanisms to improve the system

## Retry/Re-run Behavior

### Automatic Retry Options
**What User Sees**:
```
[🔄 Retry] [🔄 Retry with More Details] [❌ New Inquiry]
```

### Retry Scenarios
1. **Standard Retry**: Re-run the same inquiry (useful if system was busy)
2. **Enhanced Retry**: Prompt user to add more details before re-processing
3. **Modified Retry**: Allow user to edit original inquiry before submission

### Retry Flow
```
User clicks [🔄 Retry with More Details]
> Please provide additional details about your order issue:
> [Original: My order #12345 hasn't arrived yet. Can you help?]
> [Add details...]

[Submit Enhanced Inquiry]
```

**Benefits**:
- Allows users to improve results by providing more context
- Demonstrates system adaptability
- Gives users control over the process

## Human-in-the-Loop Escalation Point

### Escalation Triggers
- Low confidence scores from any agent (< 50%)
- High negative sentiment with complex issues
- Unknown or ambiguous request categories
- Knowledge base gaps (no relevant articles found)

### Escalation Interface
```
🚨 HUMAN ESCALATION REQUIRED
========================================

Your inquiry has been flagged for human review.

Reason: Complex technical issue with low AI confidence

Next Steps:
1. A support agent will review your case within 24 hours
2. You'll receive an email confirmation with reference ID
3. For urgent matters, call 1-800-HELP-NOW

Reference ID: ESC-2026-0426-001

[📞 Call Support Now] [📧 Request Email Update] [💬 Live Chat] [❌ Cancel]
```

### Escalation Benefits
- Ensures complex issues get proper attention
- Builds trust by admitting AI limitations
- Provides multiple contact options
- Maintains user control over escalation process

## MVP Frontend Scope

### Core Features
- **CLI Interface**: Primary interface for inquiry submission and response viewing
- **Sequential Progress Display**: Real-time agent activity visualization
- **Basic Feedback System**: Helpful/not helpful ratings
- **Retry Functionality**: Allow re-submission with modifications
- **Escalation Handling**: Clear communication of human intervention needs

### Technical Implementation
- **Python CLI**: Using argparse or simple input/output
- **Progress Bars**: Text-based progress indicators
- **Structured Output**: Clear formatting for readability
- **Error Handling**: Graceful handling of invalid inputs

### User Experience Focus
- **Clarity**: Every screen state is self-explanatory
- **Speed**: Fast response times for each agent
- **Reliability**: Consistent behavior across interactions
- **Learnability**: Intuitive flow that users can understand quickly

### Success Metrics
- Users can complete full journey in < 2 minutes
- 90% of users understand agent roles after first use
- Positive feedback on transparency features
- Low error rates in input handling

## Out of Scope

### Advanced UI Features
- Real-time chat interfaces
- Multi-user dashboards
- Advanced data visualizations
- Mobile-responsive design
- Accessibility compliance (WCAG)

### Production Elements
- User authentication and accounts
- Conversation history persistence
- Advanced analytics and reporting
- Integration with external systems
- Multi-language support

### Complex Interactions
- File uploads or attachments
- Voice input/output
- Video support
- Real-time collaboration
- Advanced personalization

### Administrative Features
- Agent configuration interfaces
- Knowledge base management UI
- System monitoring dashboards
- User management panels
- Advanced reporting tools

### Future Enhancements
- Web-based interface migration
- Progressive Web App (PWA) capabilities
- Integration with popular chat platforms
- Advanced AI model selection
- Automated learning from user feedback

This frontend design prioritizes transparency and user understanding, making the multi-agent system approachable and trustworthy while staying within the constraints of a 6-week capstone project.