class Backpressure {
  constructor(limit = 100) {
    this.queue = [];
    this.limit = limit;
  }
  enqueue(item) {
    if (this.queue.length > this.limit) {
      const err = new Error("System overloaded");
      err.code = "OVERLOADED";
      throw err;
    }
    this.queue.push(item);
  }
  dequeue() { return this.queue.shift(); }
  size() { return this.queue.length; }
}

module.exports = { Backpressure };
