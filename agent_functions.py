from livekit.agents import llm, JobContext
from livekit import rtc
from livekit.agents.voice_assistant import AgentCallContext
import asyncio


class AssistantFunction(llm.FunctionContext):
    def __init__(self, ctx: JobContext):
        super().__init__()
        self.ctx = ctx
        self.room = ctx.room
        # self.chat_manager = rtc.ChatManager(self.room)
       
    @llm.ai_callable(
        description="""
        Whenever You detect that a user wants to end the conversation
        Use this function Strictly
        """)
    async def end_conversation(self) -> None:
        try:
            agent_ctx = AgentCallContext.get_current()
            
            final_speech = await agent_ctx.agent.say("Thank you for using our services. Have a great day!", allow_interruptions=False)

            await final_speech.join()

            # Disconnect after 3 seconds
            await self.room.disconnect()

        except Exception as e:
            print(f"Error sending message: {e}")