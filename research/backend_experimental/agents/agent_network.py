class AgentNetwork:
    def __init__(self, negotiation_engine):
        self.agents = {}
        self.negotiation = negotiation_engine
        self.costs = {
            "misunderstanding": 1.0,
            "clarification_request": 0.5,
            "successful_direct_message": 0.1,
        }

    def register_agent(self, user_id: str, agent) -> None:
        self.agents[user_id] = agent

    def process_message(self, sender_id: str, receiver_id: str, text: str, context: dict) -> dict:
        sender_agent = self.agents[sender_id]
        receiver_agent = self.agents[receiver_id]
        sender_output = sender_agent.interpret(text, context)
        receiver_output = receiver_agent.interpret(text, context)
        final_output = self.negotiation.negotiate(sender_output, receiver_output)
        return final_output
