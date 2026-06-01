from crewai import Agent, Task, Crew, LLM
from dotenv import load_dotenv
import os

load_dotenv()

llm = LLM(
    model="gemini-2.0-flash",
    api_key=os.getenv("GOOGLE_API_KEY")
)

agent = Agent(
    role="Customer Support Classifier",
    goal="Classify customer support tickets",
    backstory="You help support teams understand customer issues.",
    llm=llm,
    verbose=True
)

task = Task(
    description="Classify this ticket: 'I cannot access my account.'",
    expected_output="Return the ticket category and urgency.",
    agent=agent
)

crew = Crew(
    agents=[agent],
    tasks=[task],
    verbose=True
)

result = crew.kickoff()
print(result)