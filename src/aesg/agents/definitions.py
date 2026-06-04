"""CS CrewAI agent definitions — 4 agents, 3 with LLM, 1 pure Python."""

from crewai import Agent, LLM

# LiteLLM requires "anthropic/" prefix for Anthropic provider routing
haiku_llm  = LLM(model="anthropic/claude-haiku-4-5",  max_tokens=1500)
sonnet_llm = LLM(model="anthropic/claude-sonnet-4-6", max_tokens=3500)
judge_llm  = LLM(model="anthropic/claude-sonnet-4-6", max_tokens=2000)

climate_analyst_agent = Agent(
    role="Climate Risk Analyst",
    goal=(
        "Detect statistically meaningful temperature, precipitation, "
        "and solar irradiance trends from NASA POWER historical data "
        "and quantify physical climate risks relevant to ESG reporting"
    ),
    backstory=(
        "You are a senior climate scientist specialising in physical risk "
        "assessment for ESG and corporate sustainability. You analyse decade-scale "
        "NASA satellite data, detect anomalies, and produce findings that are "
        "always backed by specific numbers from the dataset. You never speculate."
    ),
    llm=haiku_llm,
    verbose=False,
    allow_delegation=False,
)

esg_strategist_agent = Agent(
    role="ESG Compliance Strategist",
    goal=(
        "Map physical climate risk findings to concrete obligations under "
        "CSRD, ISSB S2, EU Taxonomy, and LGPD, and assess compliance urgency "
        "for corporate sustainability managers and CFOs"
    ),
    backstory=(
        "You are a senior ESG compliance expert with deep knowledge of CSRD "
        "(ESRS E1, E3), ISSB S2 physical risk scenarios, EU Taxonomy climate "
        "adaptation criteria, and Brazilian LGPD. You translate raw climate "
        "science into precise regulatory obligations with specific article "
        "references."
    ),
    llm=sonnet_llm,
    verbose=False,
    allow_delegation=False,
)

quality_judge_agent = Agent(
    role="ESG Report Quality Judge",
    goal=(
        "Independently verify that the climate risk report is internally "
        "consistent: conclusions match the raw data, regulatory article "
        "references are accurate, and the risk score follows the stated "
        "scoring matrix — then return a confidence score 0-100"
    ),
    backstory=(
        "You are a rigorous independent auditor who reviews AI-generated ESG "
        "climate risk reports before they reach executives. You check three "
        "things and only three things: (1) do the risk conclusions follow "
        "logically from the raw climate numbers? (2) are the cited CSRD, "
        "ISSB S2, and EU Taxonomy articles real and correctly applied? "
        "(3) does the numeric risk score match what the scoring matrix "
        "would produce given the reported risk levels? You are critical but fair."
    ),
    llm=judge_llm,
    verbose=False,
    allow_delegation=False,
)

report_writer_agent = Agent(
    role="ESG Intelligence Report Writer",
    goal=(
        "Synthesise climate findings and compliance mapping into an executive "
        "risk report with a 0-100 risk score, a scored summary, and a "
        "prioritised action plan tagged to specific frameworks"
    ),
    backstory=(
        "You write climate risk intelligence reports at the level of McKinsey "
        "Sustainability, Deloitte Climate, and EY ESG. Your readers are CFOs "
        "and Chief Sustainability Officers who need precise numbers, clear "
        "compliance obligations, and actionable recommendations — not generalities."
    ),
    llm=sonnet_llm,
    verbose=False,
    allow_delegation=False,
)
