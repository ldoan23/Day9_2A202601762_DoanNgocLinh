import threading


class TraceSink:
    def __init__(self, paths):
        self._lock = threading.Lock()
        self._files = []
        for path in paths:
            self._files.append(open(path, "w", encoding="utf-8"))

    def write(self, line):
        with self._lock:
            for f in self._files:
                f.write(line + "\n")
                f.flush()

    def close(self):
        for f in self._files:
            f.close()


class MessageBus:
    def __init__(self, trace_sink=None):
        self.agents = {}
        self.trace_sink = trace_sink
        self._seqs = {}
        self._lock = threading.Lock()

    def register(self, agent):
        self.agents[agent.name] = agent

    def _deliver(self, msg):
        with self._lock:
            seq = self._seqs.get(msg.conversation_id, 0) + 1
            self._seqs[msg.conversation_id] = seq
            msg.seq = seq
            if self.trace_sink is not None:
                self.trace_sink.write(msg.to_json_line())

    def send(self, msg):
        self._deliver(msg)
        agent = self.agents.get(msg.recipient)
        if agent is None:
            raise KeyError("no agent registered under %r" % (msg.recipient,))
        response = agent.handle(msg)
        self._deliver(response)
        return response
