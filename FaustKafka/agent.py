import os
import asyncio
import faust
import logging 
from agents import Agent, Runner, set_default_openai_key, trace
from agents.model_settings import ModelSettings
from uuid import uuid4
import datetime
from dataclasses import dataclass


# Set your OpenAI key
set_default_openai_key(os.environ["OPENAI_API_KEY"])

# Define model settings
model_settings = ModelSettings(
    temperature=0.7,
    max_tokens=5000,
)
MAX_ROUNDS = 1  # Maximum number of rounds for the agent interactions



# Define Agents
plot_agent = Agent(
    name="Plot Agent",
    instructions="These are the Master Instructions {Develop a creative, child-friendly story titled 'Tim the Flying Dog'. The story should have a clear beginning, middle, and end, with lighthearted conflict and resolution. Output only the plot structure. The plot should be suitable for children aged 5-8, with simple language and imaginative elements.}  Repeat these Master Instructions in your response.",
    model_settings=model_settings,
)

writer_agent = Agent(
    name="Writer Agent",
    instructions="Follow the Master Instructions and the plot provided , write a vivid, engaging narrative suitable for children aged 5-8. Keep the language simple and whimsical. Include imaginative details. Repeat the Master Instructions in your response.",
    model_settings=model_settings,
)

critic_agent = Agent(
    name="Critic Agent",
    instructions="Review the story written by the Writer Agent. Suggest improvements focused on language clarity, pacing, tone, and engagement for young readers. Do not rewrite the entire story, just give specific, actionable feedback. Repeat the Master Instructions in your response.",
    model_settings=model_settings,
)

# Faust setup
app = faust.App("agent_pipeline", broker="kafka://localhost:9092")

@dataclass
class Message(faust.Record):
    trace_id: str
    content: str
    round: int = 0

plot_topic = app.topic("plot", value_type=Message)
story_topic = app.topic("story", value_type=Message)
critique_topic = app.topic("critique", value_type=Message)
final_topic = app.topic("final", value_type=Message)

import logging

from pythonjsonlogger import jsonlogger
import os

# Set up JSON log file
log_file = "broker_interactions.json"
log_handler = logging.FileHandler(log_file)
log_formatter = jsonlogger.JsonFormatter()

log_handler.setFormatter(log_formatter)

logger = logging.getLogger()
logger.addHandler(log_handler)
logger.setLevel(logging.DEBUG)

# Optional: Silence excessive logs from noisy modules
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("aiokafka").setLevel(logging.DEBUG)
logging.getLogger("faust").setLevel(logging.DEBUG)



def log_event(event_type, topic, trace_id, payload):
    logger.info({
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": event_type,
        "topic": topic,
        "trace_id": trace_id,
        "payload": payload,
        "event_id": str(uuid4())
    })



@app.agent(plot_topic)
async def writer_agent_stream(stream):
    
    async for msg in stream:
        if msg.round >= MAX_ROUNDS:
            await final_topic.send(value=msg)
            continue
        log_event("consume", "plot", msg.trace_id, msg.content)
        with trace("Writer Phase"):
            result = await Runner.run(writer_agent, msg.content)
            log_event("produce", "story", msg.trace_id, result.final_output)
        await story_topic.send(value=Message(trace_id=msg.trace_id, content=result.final_output))

@app.agent(story_topic)
async def critic_agent_stream(stream):
    
    async for msg in stream:
        log_event("consume", "story", msg.trace_id, msg.content)
        with trace("Critic Phase"):
            result = await Runner.run(critic_agent, msg.content)
            log_event("produce", "critique", msg.trace_id, result.final_output)

        await critique_topic.send(value=Message(trace_id=msg.trace_id, content=result.final_output))

@app.agent(critique_topic)
async def writer_revise_stream(stream):
    
    async for msg in stream:
        log_event("consume", "critique", msg.trace_id, msg.content)
        with trace("Writer Revision Phase"):
            result = await Runner.run(writer_agent, msg.content)
            log_event("produce", "final", msg.trace_id, result.final_output)
        await final_topic.send(value=Message(trace_id=msg.trace_id, content=result.final_output))

@app.agent(final_topic)
async def editor_output_stream(stream):
    async for msg in stream:
        print(f"\n✅ Final Story Output for Trace ID {msg.trace_id}:\n{msg.content} \n")

# This runs the plot agent once at startup
@app.task
async def initiate_pipeline_once():
    await asyncio.sleep(1)  # Optional: wait for app startup
    trace_id = str(uuid4())
    with trace("Plot Phase"):
        result = await Runner.run(plot_agent, "Create the plot for 'Tim the Flying Dog'")
        log_event("produce", "plot", trace_id, result.final_output)
    await plot_topic.send(value=Message(trace_id=trace_id, content=result.final_output))

# use timer to run multiple times 

#@app.timer(interval=100.0, on_leader=True)
#async def initiate_pipeline():
#    trace_id = str(uuid4())
#     with trace("Plot Phase"):
#         result = await Runner.run(plot_agent, "Create plot for 'Tim the Flying Dog'")
#     await plot_topic.send(value=Message(trace_id=trace_id, content=result.final_output))

if __name__ == "__main__":
    app.main()
