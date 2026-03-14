package tpcp

// DLQ is a Dead Letter Queue backed by a buffered channel (capacity 100).
// Envelopes that have no registered handler are deposited here.
type DLQ struct {
	ch chan *TPCPEnvelope
}

// NewDLQ creates a DLQ with capacity 100.
func NewDLQ() *DLQ {
	return &DLQ{ch: make(chan *TPCPEnvelope, 100)}
}

// Enqueue adds an envelope to the queue. Returns false if the queue is full.
func (q *DLQ) Enqueue(env *TPCPEnvelope) bool {
	select {
	case q.ch <- env:
		return true
	default:
		return false
	}
}

// Drain removes and returns all envelopes currently in the queue.
func (q *DLQ) Drain() []*TPCPEnvelope {
	var out []*TPCPEnvelope
	for {
		select {
		case env := <-q.ch:
			out = append(out, env)
		default:
			return out
		}
	}
}

// Len returns the number of envelopes currently queued.
func (q *DLQ) Len() int {
	return len(q.ch)
}
