class MemoryGraph {
  constructor() {
    this.graph = {};
  }

  _key(a, b) {
    return `${a}-${b}`;
  }

  link(userA, userB, data = {}) {
    const key = this._key(userA, userB);
    if (!this.graph[key]) {
      this.graph[key] = { misunderstandings: 0, clarity_success: 0, topics: [] };
    }
    const edge = this.graph[key];
    if (data.misunderstanding) edge.misunderstandings++;
    if (data.success) edge.clarity_success++;
    if (data.topic) edge.topics.push(data.topic);
  }

  getRelationship(userA, userB) {
    return this.graph[this._key(userA, userB)] || null;
  }
}

module.exports = { MemoryGraph };
