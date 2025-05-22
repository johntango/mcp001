import os
import asyncio
from agents import Agent, Runner, set_default_openai_key, gen_trace_id, trace
from agents.mcp import MCPServerSse, MCPServerSseParams
from agents.model_settings import ModelSettings

# Set your OpenAI key
set_default_openai_key(os.environ["OPENAI_API_KEY"])

# Define common model settings
model_settings = ModelSettings(
    temperature=0.7,
    max_tokens=5000,
)

# --- Define Agents ---


plot_agent = Agent(
    name="Plot Agent",
    instructions="Develop a creative, child-friendly plot for a story titled 'Tim the Flying Dog'. The story should have a clear beginning, middle, and end, with lighthearted conflict and resolution. Output only the plot structure.",
    model_settings=model_settings,
)

writer_agent = Agent(
    name="Writer Agent",
    instructions="Using the plot provided, write a vivid, engaging narrative suitable for children aged 5-8. Keep the language simple and whimsical. Include imaginative details.",
    model_settings=model_settings,
)

critic_agent = Agent(
    name="Critic Agent",
    instructions="Review the story written by the Writer Agent. Suggest improvements focused on language clarity, pacing, tone, and engagement for young readers. Do not rewrite the entire story, just give specific, actionable feedback.",
    model_settings=model_settings,
)

editor_agent = Agent(
    name="Editor Agent",
    instructions=(
        "You are the Editor coordinating the children's book 'Tim the Flying Dog'. "
        "Begin by asking the Plot Agent Tool to create a plot. Then pass the plot to the Writer Agent Tool to write the story. "
        "Next, give the story to the Critic Agent Tool for feedback. "
        "Then ask the Writer Agent to revise the story based on the Critic's feedback. "
        "Finally, send results back and print out the final book. "
        "Respond at each stage using structured outputs like {stage: ..., content: ...}."
    ),
    model_settings=model_settings,
    tools=[
        plot_agent.as_tool(
            tool_name="PlotAgent",
            tool_description="Develop an outline plot that the writer can use to write the story.",
        ),
        writer_agent.as_tool(
            tool_name="WriterAgent",
            tool_description="Write the story based on the plot provided by the Plot Agent.",
        ),
        critic_agent.as_tool(
            tool_name="CriticAgent",
            tool_description="Review the story written by the Writer Agent and provide feedback.",
        ),
    ],
    # handoffs=[plot_agent, writer_agent, critic_agent]
)
def trace_hook(trace):
    for step in trace.steps:
        print(f"\n🔧 Agent: {step.agent.name}")
        print(f"➡️ Input: {step.input.content}")
        print(f"✅ Output: {step.output.content}")
# --- Runner Execution ---

async def run_book_creation():
    input_prompt = "Please coordinate the book creation process for 'Tim the Flying Dog'."
    print(f">> Running Editor Agent with input: {input_prompt}")

    try:
        # run trace
        with trace("Book creation workflow"):
            editor_result = await Runner.run(editor_agent, input_prompt)
            # print trace
            print(f"\n\nFinal response:\n{editor_result.final_output}")
            print("\n✅ Final Book Output:\n")
            print(editor_result.final_output)
    except TimeoutError:
        print("❌ Timed out during the agent orchestration")

# Entry point
if __name__ == "__main__":
    asyncio.run(run_book_creation())
