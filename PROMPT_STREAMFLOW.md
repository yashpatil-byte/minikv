# PROMPT: StreamFlow - Production-Grade Distributed Stream Processing Engine

## Mission
Build a distributed, real-time stream processing framework in Go that demonstrates mastery of windowing, stateful computations, and fault-tolerant data pipelines. Target: 150K+ events/sec throughput with <50ms P99 latency.

---

## What is Stream Processing?

**Key Concept**: Process **infinite streams** of data in real-time with transformations, aggregations, and time-based windowing.

**Difference from Batch Processing**:
- Batch: Process all data at once (Hadoop, Spark batch)
- Stream: Process data as it arrives (Flink, Storm, Kafka Streams)

**Example Use Cases**:
- Real-time analytics (dashboard updates every second)
- Fraud detection (flag suspicious transactions immediately)
- IoT monitoring (aggregate sensor readings every 60 seconds)
- Log processing (parse, filter, route logs)

---

## Core Concepts

### 1. **Events**
```go
type Event struct {
    Key       string                 // Partition key (e.g., user_id)
    Value     map[string]interface{} // Event data
    Timestamp int64                  // Unix timestamp (ms)
    Metadata  map[string]string      // Optional metadata
}
```

### 2. **Operators** (Transformations)

| Operator | Input → Output | Example |
|----------|----------------|---------|
| **Map** | 1 → 1 | `event.price * 1.1` (add 10% tax) |
| **Filter** | 1 → 0 or 1 | Keep only `price > 100` |
| **FlatMap** | 1 → N | Split sentence into words |
| **Reduce** | N → 1 | Sum all prices |
| **Aggregate** | N → 1 (per window) | Count events per minute |

### 3. **Windowing** (CRITICAL)

**Why?** Can't process infinite stream all at once. Split into finite chunks.

#### **Tumbling Windows** (Fixed, non-overlapping)
```
Time: 0s────60s────120s────180s
      [──W1──][──W2──][──W3──]

Example: Count page views per minute
  - Window 1 (0-60s): 1,234 views
  - Window 2 (60-120s): 987 views
```

#### **Sliding Windows** (Fixed size, overlapping)
```
Time: 0s────30s────60s────90s────120s
      [────Window 1────]
               [────Window 2────]
                        [────Window 3────]

Example: Moving average (5-minute window, slide 1 minute)
```

#### **Session Windows** (Gap-based, variable size)
```
Events: ──•─•──•──────────•─•─•──────────────•──
        [Session 1]     [Session 2]      [Session 3]
        
Example: User session (gap = 5 minutes inactivity)
  - Session 1: 3 events, duration 10s
  - Session 2: 3 events, duration 8s
  - Session 3: 1 event
```

### 4. **State**

Some operators need memory:
- **Count**: Track current count
- **Sum**: Track running sum
- **Deduplication**: Remember seen IDs
- **Join**: Buffer events from both streams

State must be:
- ✅ Fault-tolerant (persisted to disk)
- ✅ Recoverable (checkpoint + replay)
- ✅ Efficient (fast lookups)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          StreamFlow                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐        ┌─────────────┐        ┌───────────┐      │
│  │ Sources  │───────>│  Operators  │───────>│  Sinks    │      │
│  ├──────────┤        ├─────────────┤        ├───────────┤      │
│  │ Kafka    │        │ Map         │        │ Kafka     │      │
│  │ HTTP     │        │ Filter      │        │ MiniKV    │      │
│  │ File     │        │ FlatMap     │        │ File      │      │
│  │ Generator│        │ Reduce      │        │ HTTP      │      │
│  └──────────┘        │ Aggregate   │        │ Stdout    │      │
│                      └─────────────┘        └───────────┘      │
│                             │                                    │
│                      ┌──────▼────────┐                          │
│                      │   Windowing   │                          │
│                      ├───────────────┤                          │
│                      │ Tumbling      │                          │
│                      │ Sliding       │                          │
│                      │ Session       │                          │
│                      └───────────────┘                          │
│                             │                                    │
│                      ┌──────▼────────┐                          │
│                      │     State     │                          │
│                      ├───────────────┤                          │
│                      │ In-Memory     │                          │
│                      │ BoltDB        │                          │
│                      │ Checkpointing │                          │
│                      └───────────────┘                          │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Execution Engine                           │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │ • Multi-worker parallelism (4-8 workers)               │    │
│  │ • Task scheduling & distribution                        │    │
│  │ • Backpressure handling                                 │    │
│  │ • Checkpoint coordination                               │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Core Pipeline (Week 1-2)

#### 1.1 Event Data Model

Create `pkg/event/event.go`:
```go
package event

import "time"

// Event represents a single data record in the stream
type Event struct {
    Key       string                 // Partition key
    Value     map[string]interface{} // Event payload
    Timestamp int64                  // Event time (Unix milliseconds)
    Metadata  map[string]string      // Optional metadata
}

// NewEvent creates a new event with current timestamp
func NewEvent(key string, value map[string]interface{}) *Event {
    return &Event{
        Key:       key,
        Value:     value,
        Timestamp: time.Now().UnixMilli(),
        Metadata:  make(map[string]string),
    }
}

// WithTimestamp sets a custom timestamp
func (e *Event) WithTimestamp(ts int64) *Event {
    e.Timestamp = ts
    return e
}

// Clone creates a deep copy
func (e *Event) Clone() *Event {
    cloned := &Event{
        Key:       e.Key,
        Timestamp: e.Timestamp,
        Value:     make(map[string]interface{}),
        Metadata:  make(map[string]string),
    }
    
    for k, v := range e.Value {
        cloned.Value[k] = v
    }
    for k, v := range e.Metadata {
        cloned.Metadata[k] = v
    }
    
    return cloned
}
```

#### 1.2 Operators (Transformations)

Create `pkg/operator/operator.go`:
```go
package operator

import "streamflow/pkg/event"

// Operator is the interface all transformations implement
type Operator interface {
    Process(in <-chan *event.Event, out chan<- *event.Event)
    Name() string
}

// MapFunc transforms one event to another
type MapFunc func(*event.Event) *event.Event

// MapOperator applies a function to each event
type MapOperator struct {
    name string
    fn   MapFunc
}

func NewMapOperator(name string, fn MapFunc) *MapOperator {
    return &MapOperator{name: name, fn: fn}
}

func (m *MapOperator) Process(in <-chan *event.Event, out chan<- *event.Event) {
    for evt := range in {
        transformed := m.fn(evt)
        if transformed != nil {
            out <- transformed
        }
    }
    close(out)
}

func (m *MapOperator) Name() string {
    return m.name
}

// FilterFunc returns true if event should be kept
type FilterFunc func(*event.Event) bool

// FilterOperator filters events based on predicate
type FilterOperator struct {
    name string
    fn   FilterFunc
}

func NewFilterOperator(name string, fn FilterFunc) *FilterOperator {
    return &FilterOperator{name: name, fn: fn}
}

func (f *FilterOperator) Process(in <-chan *event.Event, out chan<- *event.Event) {
    for evt := range in {
        if f.fn(evt) {
            out <- evt
        }
    }
    close(out)
}

func (f *FilterOperator) Name() string {
    return f.name
}

// FlatMapFunc transforms one event into multiple events
type FlatMapFunc func(*event.Event) []*event.Event

// FlatMapOperator expands one event into many
type FlatMapOperator struct {
    name string
    fn   FlatMapFunc
}

func NewFlatMapOperator(name string, fn FlatMapFunc) *FlatMapOperator {
    return &FlatMapOperator{name: name, fn: fn}
}

func (fm *FlatMapOperator) Process(in <-chan *event.Event, out chan<- *event.Event) {
    for evt := range in {
        results := fm.fn(evt)
        for _, result := range results {
            out <- result
        }
    }
    close(out)
}

func (fm *FlatMapOperator) Name() string {
    return fm.name
}
```

#### 1.3 Sources

Create `pkg/source/source.go`:
```go
package source

import (
    "bufio"
    "encoding/json"
    "os"
    "streamflow/pkg/event"
    "time"
)

// Source produces events into the pipeline
type Source interface {
    Start(out chan<- *event.Event) error
    Stop() error
}

// FileSource reads events from a file (one JSON per line)
type FileSource struct {
    filepath string
    running  bool
}

func NewFileSource(filepath string) *FileSource {
    return &FileSource{filepath: filepath}
}

func (f *FileSource) Start(out chan<- *event.Event) error {
    f.running = true
    
    file, err := os.Open(f.filepath)
    if err != nil {
        return err
    }
    defer file.Close()
    
    scanner := bufio.NewScanner(file)
    for scanner.Scan() && f.running {
        var data map[string]interface{}
        if err := json.Unmarshal(scanner.Bytes(), &data); err != nil {
            continue
        }
        
        evt := event.NewEvent("", data)
        out <- evt
    }
    
    close(out)
    return scanner.Err()
}

func (f *FileSource) Stop() error {
    f.running = false
    return nil
}

// GeneratorSource generates synthetic events (for testing)
type GeneratorSource struct {
    rate    int    // events per second
    duration time.Duration
    running bool
}

func NewGeneratorSource(rate int, duration time.Duration) *GeneratorSource {
    return &GeneratorSource{rate: rate, duration: duration}
}

func (g *GeneratorSource) Start(out chan<- *event.Event) error {
    g.running = true
    
    ticker := time.NewTicker(time.Second / time.Duration(g.rate))
    defer ticker.Stop()
    
    timeout := time.After(g.duration)
    
    i := 0
    for g.running {
        select {
        case <-ticker.C:
            evt := event.NewEvent(
                "key",
                map[string]interface{}{
                    "id":    i,
                    "value": i * 10,
                },
            )
            out <- evt
            i++
        case <-timeout:
            g.running = false
        }
    }
    
    close(out)
    return nil
}

func (g *GeneratorSource) Stop() error {
    g.running = false
    return nil
}
```

#### 1.4 Sinks

Create `pkg/sink/sink.go`:
```go
package sink

import (
    "encoding/json"
    "fmt"
    "os"
    "streamflow/pkg/event"
)

// Sink consumes events from the pipeline
type Sink interface {
    Write(evt *event.Event) error
    Close() error
}

// StdoutSink prints events to stdout
type StdoutSink struct{}

func NewStdoutSink() *StdoutSink {
    return &StdoutSink{}
}

func (s *StdoutSink) Write(evt *event.Event) error {
    json, _ := json.Marshal(evt)
    fmt.Println(string(json))
    return nil
}

func (s *StdoutSink) Close() error {
    return nil
}

// FileSink writes events to a file
type FileSink struct {
    filepath string
    file     *os.File
}

func NewFileSink(filepath string) *FileSink {
    return &FileSink{filepath: filepath}
}

func (f *FileSink) Write(evt *event.Event) error {
    if f.file == nil {
        file, err := os.OpenFile(f.filepath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
        if err != nil {
            return err
        }
        f.file = file
    }
    
    json, _ := json.Marshal(evt)
    _, err := f.file.WriteString(string(json) + "\n")
    return err
}

func (f *FileSink) Close() error {
    if f.file != nil {
        return f.file.Close()
    }
    return nil
}
```

#### 1.5 Pipeline Builder

Create `pkg/stream/stream.go`:
```go
package stream

import (
    "streamflow/pkg/event"
    "streamflow/pkg/operator"
    "streamflow/pkg/sink"
    "streamflow/pkg/source"
)

// Stream represents a data processing pipeline
type Stream struct {
    source    source.Source
    operators []operator.Operator
    sink      sink.Sink
}

// NewStream creates a new stream from a source
func NewStream(src source.Source) *Stream {
    return &Stream{
        source:    src,
        operators: make([]operator.Operator, 0),
    }
}

// Map applies a transformation to each event
func (s *Stream) Map(fn operator.MapFunc) *Stream {
    s.operators = append(s.operators, operator.NewMapOperator("map", fn))
    return s
}

// Filter keeps only events matching predicate
func (s *Stream) Filter(fn operator.FilterFunc) *Stream {
    s.operators = append(s.operators, operator.NewFilterOperator("filter", fn))
    return s
}

// FlatMap expands one event into many
func (s *Stream) FlatMap(fn operator.FlatMapFunc) *Stream {
    s.operators = append(s.operators, operator.NewFlatMapOperator("flatmap", fn))
    return s
}

// Sink sets the output destination
func (s *Stream) Sink(snk sink.Sink) *Stream {
    s.sink = snk
    return s
}

// Run executes the pipeline
func (s *Stream) Run() error {
    // Create channels connecting operators
    channels := make([]chan *event.Event, len(s.operators)+1)
    for i := range channels {
        channels[i] = make(chan *event.Event, 100) // Buffered
    }
    
    // Start source
    go s.source.Start(channels[0])
    
    // Start operators (chain them together)
    for i, op := range s.operators {
        go op.Process(channels[i], channels[i+1])
    }
    
    // Consume from last channel and write to sink
    lastChannel := channels[len(channels)-1]
    for evt := range lastChannel {
        if err := s.sink.Write(evt); err != nil {
            return err
        }
    }
    
    return s.sink.Close()
}
```

#### 1.6 Example Usage

Create `examples/simple_pipeline.go`:
```go
package main

import (
    "fmt"
    "streamflow/pkg/event"
    "streamflow/pkg/sink"
    "streamflow/pkg/source"
    "streamflow/pkg/stream"
    "time"
)

func main() {
    // Create a pipeline
    src := source.NewGeneratorSource(1000, 10*time.Second) // 1000 events/sec for 10s
    
    pipeline := stream.NewStream(src).
        Filter(func(evt *event.Event) bool {
            // Keep only events where value > 50
            value := evt.Value["value"].(int)
            return value > 50
        }).
        Map(func(evt *event.Event) *event.Event {
            // Double the value
            evt.Value["doubled"] = evt.Value["value"].(int) * 2
            return evt
        }).
        Sink(sink.NewStdoutSink())
    
    fmt.Println("Starting pipeline...")
    if err := pipeline.Run(); err != nil {
        fmt.Printf("Error: %v\n", err)
    }
    fmt.Println("Pipeline completed")
}
```

**Milestone 1**: Basic pipeline working (Source → Map → Filter → Sink)

---

### Phase 2: Windowing (Week 3-4)

#### 2.1 Window Definitions

Create `pkg/window/window.go`:
```go
package window

import "time"

// WindowType defines the windowing strategy
type WindowType int

const (
    Tumbling WindowType = iota // Fixed, non-overlapping
    Sliding                     // Fixed size, overlapping
    Session                     // Gap-based, variable size
)

// WindowSpec specifies windowing parameters
type WindowSpec struct {
    Type     WindowType
    Size     time.Duration // Window size
    Slide    time.Duration // Slide interval (for sliding windows)
    GapTime  time.Duration // Inactivity gap (for session windows)
}

// NewTumblingWindow creates fixed windows
func NewTumblingWindow(size time.Duration) *WindowSpec {
    return &WindowSpec{
        Type: Tumbling,
        Size: size,
    }
}

// NewSlidingWindow creates overlapping windows
func NewSlidingWindow(size, slide time.Duration) *WindowSpec {
    return &WindowSpec{
        Type:  Sliding,
        Size:  size,
        Slide: slide,
    }
}

// NewSessionWindow creates gap-based windows
func NewSessionWindow(gap time.Duration) *WindowSpec {
    return &WindowSpec{
        Type:    Session,
        GapTime: gap,
    }
}

// Window represents a time window with start and end
type Window struct {
    Start int64 // Start time (Unix ms)
    End   int64 // End time (Unix ms)
}

// Contains checks if timestamp falls in window
func (w *Window) Contains(timestamp int64) bool {
    return timestamp >= w.Start && timestamp < w.End
}

// WindowAssigner assigns events to windows
type WindowAssigner interface {
    AssignWindows(eventTime int64) []*Window
}

// TumblingWindowAssigner assigns to single non-overlapping window
type TumblingWindowAssigner struct {
    size time.Duration
}

func NewTumblingWindowAssigner(size time.Duration) *TumblingWindowAssigner {
    return &TumblingWindowAssigner{size: size}
}

func (t *TumblingWindowAssigner) AssignWindows(eventTime int64) []*Window {
    sizeMs := t.size.Milliseconds()
    start := (eventTime / sizeMs) * sizeMs
    end := start + sizeMs
    
    return []*Window{{Start: start, End: end}}
}

// SlidingWindowAssigner assigns to multiple overlapping windows
type SlidingWindowAssigner struct {
    size  time.Duration
    slide time.Duration
}

func NewSlidingWindowAssigner(size, slide time.Duration) *SlidingWindowAssigner {
    return &SlidingWindowAssigner{size: size, slide: slide}
}

func (s *SlidingWindowAssigner) AssignWindows(eventTime int64) []*Window {
    sizeMs := s.size.Milliseconds()
    slideMs := s.slide.Milliseconds()
    
    // Calculate which windows this event belongs to
    firstWindowStart := (eventTime / slideMs) * slideMs
    
    windows := make([]*Window, 0)
    
    // Generate all windows that contain this event
    for windowStart := firstWindowStart; windowStart > eventTime-sizeMs; windowStart -= slideMs {
        if windowStart <= eventTime {
            windows = append(windows, &Window{
                Start: windowStart,
                End:   windowStart + sizeMs,
            })
        }
    }
    
    return windows
}
```

#### 2.2 Windowed Operators

Create `pkg/operator/windowed.go`:
```go
package operator

import (
    "streamflow/pkg/event"
    "streamflow/pkg/window"
    "sync"
    "time"
)

// WindowedStream groups events by windows
type WindowedStream struct {
    assigner window.WindowAssigner
    windows  map[int64][]*event.Event // key: window_start_time
    mu       sync.RWMutex
}

func NewWindowedStream(assigner window.WindowAssigner) *WindowedStream {
    return &WindowedStream{
        assigner: assigner,
        windows:  make(map[int64][]*event.Event),
    }
}

// AddEvent assigns event to window(s)
func (w *WindowedStream) AddEvent(evt *event.Event) {
    windows := w.assigner.AssignWindows(evt.Timestamp)
    
    w.mu.Lock()
    defer w.mu.Unlock()
    
    for _, win := range windows {
        w.windows[win.Start] = append(w.windows[win.Start], evt)
    }
}

// AggregateFunc combines events in a window
type AggregateFunc func([]*event.Event) *event.Event

// Count aggregator
func Count() AggregateFunc {
    return func(events []*event.Event) *event.Event {
        return event.NewEvent(
            "count",
            map[string]interface{}{
                "count": len(events),
            },
        )
    }
}

// Sum aggregator
func Sum(field string) AggregateFunc {
    return func(events []*event.Event) *event.Event {
        sum := 0
        for _, evt := range events {
            if val, ok := evt.Value[field].(int); ok {
                sum += val
            }
        }
        return event.NewEvent(
            "sum",
            map[string]interface{}{
                "sum": sum,
            },
        )
    }
}

// Aggregate applies function to each completed window
func (w *WindowedStream) Aggregate(fn AggregateFunc, out chan<- *event.Event) {
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop()
    
    for range ticker.C {
        now := time.Now().UnixMilli()
        
        w.mu.Lock()
        
        // Find windows that have ended
        for windowStart, events := range w.windows {
            // If window ended more than 1 second ago, process it
            if now > windowStart+60000 { // Assuming 60s window
                result := fn(events)
                result.Value["window_start"] = windowStart
                result.Value["window_end"] = windowStart + 60000
                out <- result
                
                delete(w.windows, windowStart)
            }
        }
        
        w.mu.Unlock()
    }
}
```

#### 2.3 Update Stream API

Update `pkg/stream/stream.go`:
```go
// Window creates a windowed stream
func (s *Stream) Window(spec *window.WindowSpec) *WindowedStream {
    var assigner window.WindowAssigner
    
    switch spec.Type {
    case window.Tumbling:
        assigner = window.NewTumblingWindowAssigner(spec.Size)
    case window.Sliding:
        assigner = window.NewSlidingWindowAssigner(spec.Size, spec.Slide)
    // ... session windows
    }
    
    windowed := operator.NewWindowedStream(assigner)
    
    // ... chain into pipeline
    
    return windowed
}
```

**Milestone 2**: Tumbling and sliding windows working with aggregations

---

### Phase 3: State Management (Week 5-6)

#### 3.1 State Store

Create `pkg/state/state.go`:
```go
package state

import (
    "encoding/json"
    bolt "go.etcd.io/bbolt"
)

// StateStore provides fault-tolerant state storage
type StateStore interface {
    Get(key string) (interface{}, error)
    Put(key string, value interface{}) error
    Delete(key string) error
    Checkpoint() error
    Restore() error
}

// BoltDBStore uses BoltDB for persistence
type BoltDBStore struct {
    db         *bolt.DB
    bucketName string
}

func NewBoltDBStore(filepath string) (*BoltDBStore, error) {
    db, err := bolt.Open(filepath, 0600, nil)
    if err != nil {
        return nil, err
    }
    
    store := &BoltDBStore{
        db:         db,
        bucketName: "streamflow_state",
    }
    
    // Create bucket
    err = db.Update(func(tx *bolt.Tx) error {
        _, err := tx.CreateBucketIfNotExists([]byte(store.bucketName))
        return err
    })
    
    return store, err
}

func (b *BoltDBStore) Get(key string) (interface{}, error) {
    var value interface{}
    
    err := b.db.View(func(tx *bolt.Tx) error {
        bucket := tx.Bucket([]byte(b.bucketName))
        data := bucket.Get([]byte(key))
        if data == nil {
            return nil
        }
        return json.Unmarshal(data, &value)
    })
    
    return value, err
}

func (b *BoltDBStore) Put(key string, value interface{}) error {
    return b.db.Update(func(tx *bolt.Tx) error {
        bucket := tx.Bucket([]byte(b.bucketName))
        data, err := json.Marshal(value)
        if err != nil {
            return err
        }
        return bucket.Put([]byte(key), data)
    })
}

func (b *BoltDBStore) Delete(key string) error {
    return b.db.Update(func(tx *bolt.Tx) error {
        bucket := tx.Bucket([]byte(b.bucketName))
        return bucket.Delete([]byte(key))
    })
}

func (b *BoltDBStore) Checkpoint() error {
    return b.db.Sync()
}

func (b *BoltDBStore) Restore() error {
    // State is automatically restored when opening BoltDB
    return nil
}

func (b *BoltDBStore) Close() error {
    return b.db.Close()
}
```

#### 3.2 Stateful Operators

Create `pkg/operator/stateful.go`:
```go
package operator

import (
    "streamflow/pkg/event"
    "streamflow/pkg/state"
)

// ReduceOperator maintains running state
type ReduceOperator struct {
    name    string
    fn      func(acc, curr interface{}) interface{}
    initial interface{}
    state   state.StateStore
}

func NewReduceOperator(name string, fn func(acc, curr interface{}) interface{}, initial interface{}, store state.StateStore) *ReduceOperator {
    return &ReduceOperator{
        name:    name,
        fn:      fn,
        initial: initial,
        state:   store,
    }
}

func (r *ReduceOperator) Process(in <-chan *event.Event, out chan<- *event.Event) {
    // Restore state from checkpoint
    acc, err := r.state.Get("accumulator")
    if err != nil || acc == nil {
        acc = r.initial
    }
    
    for evt := range in {
        // Update accumulator
        acc = r.fn(acc, evt.Value)
        
        // Save state
        r.state.Put("accumulator", acc)
        
        // Emit updated result
        result := evt.Clone()
        result.Value["accumulator"] = acc
        out <- result
    }
    
    // Final checkpoint
    r.state.Checkpoint()
    close(out)
}

func (r *ReduceOperator) Name() string {
    return r.name
}
```

#### 3.3 Checkpointing

Create `pkg/checkpoint/checkpoint.go`:
```go
package checkpoint

import (
    "streamflow/pkg/state"
    "time"
)

// Coordinator manages periodic checkpoints
type Coordinator struct {
    stores   []state.StateStore
    interval time.Duration
    stopCh   chan struct{}
}

func NewCoordinator(interval time.Duration) *Coordinator {
    return &Coordinator{
        stores:   make([]state.StateStore, 0),
        interval: interval,
        stopCh:   make(chan struct{}),
    }
}

func (c *Coordinator) RegisterStore(store state.StateStore) {
    c.stores = append(c.stores, store)
}

func (c *Coordinator) Start() {
    go func() {
        ticker := time.NewTicker(c.interval)
        defer ticker.Stop()
        
        for {
            select {
            case <-ticker.C:
                c.performCheckpoint()
            case <-c.stopCh:
                return
            }
        }
    }()
}

func (c *Coordinator) performCheckpoint() {
    for _, store := range c.stores {
        if err := store.Checkpoint(); err != nil {
            // Log error
        }
    }
}

func (c *Coordinator) Stop() {
    close(c.stopCh)
}
```

**Milestone 3**: Stateful processing with checkpoints, survive crashes

---

### Phase 4: Parallelism (Week 7-8)

#### 4.1 Worker Pool

Create `pkg/executor/executor.go`:
```go
package executor

import (
    "streamflow/pkg/event"
    "streamflow/pkg/operator"
    "sync"
)

// Executor manages parallel execution
type Executor struct {
    numWorkers int
    operators  []operator.Operator
}

func NewExecutor(numWorkers int) *Executor {
    return &Executor{
        numWorkers: numWorkers,
        operators:  make([]operator.Operator, 0),
    }
}

// ExecuteParallel runs operator with multiple workers
func (e *Executor) ExecuteParallel(op operator.Operator, in <-chan *event.Event, out chan<- *event.Event) {
    var wg sync.WaitGroup
    
    // Create per-worker channels
    workerInputs := make([]chan *event.Event, e.numWorkers)
    workerOutputs := make([]chan *event.Event, e.numWorkers)
    
    for i := 0; i < e.numWorkers; i++ {
        workerInputs[i] = make(chan *event.Event, 100)
        workerOutputs[i] = make(chan *event.Event, 100)
    }
    
    // Start workers
    for i := 0; i < e.numWorkers; i++ {
        wg.Add(1)
        go func(idx int) {
            defer wg.Done()
            op.Process(workerInputs[idx], workerOutputs[idx])
        }(i)
    }
    
    // Distribute input events by key hash
    go func() {
        for evt := range in {
            workerIdx := hash(evt.Key) % e.numWorkers
            workerInputs[workerIdx] <- evt
        }
        
        // Close all worker inputs
        for i := 0; i < e.numWorkers; i++ {
            close(workerInputs[i])
        }
    }()
    
    // Merge worker outputs
    go func() {
        wg.Wait()
        for i := 0; i < e.numWorkers; i++ {
            close(workerOutputs[i])
        }
    }()
    
    // Collect from all workers
    for i := 0; i < e.numWorkers; i++ {
        go func(idx int) {
            for evt := range workerOutputs[idx] {
                out <- evt
            }
        }(i)
    }
}

func hash(key string) int {
    h := 0
    for _, c := range key {
        h = 31*h + int(c)
    }
    if h < 0 {
        h = -h
    }
    return h
}
```

#### 4.2 Backpressure

Create `pkg/backpressure/backpressure.go`:
```go
package backpressure

import (
    "streamflow/pkg/event"
    "time"
)

// RateLimiter implements backpressure
type RateLimiter struct {
    maxRate   int           // events per second
    burstSize int           // max burst
    tokens    chan struct{} // token bucket
}

func NewRateLimiter(maxRate, burstSize int) *RateLimiter {
    rl := &RateLimiter{
        maxRate:   maxRate,
        burstSize: burstSize,
        tokens:    make(chan struct{}, burstSize),
    }
    
    // Fill bucket initially
    for i := 0; i < burstSize; i++ {
        rl.tokens <- struct{}{}
    }
    
    // Refill tokens periodically
    go rl.refill()
    
    return rl
}

func (rl *RateLimiter) refill() {
    ticker := time.NewTicker(time.Second / time.Duration(rl.maxRate))
    defer ticker.Stop()
    
    for range ticker.C {
        select {
        case rl.tokens <- struct{}{}:
        default:
            // Bucket full
        }
    }
}

func (rl *RateLimiter) Allow() bool {
    select {
    case <-rl.tokens:
        return true
    default:
        return false
    }
}

func (rl *RateLimiter) Wait() {
    <-rl.tokens
}

// BufferedChannel with backpressure
type BufferedChannel struct {
    ch      chan *event.Event
    limiter *RateLimiter
}

func NewBufferedChannel(size int, maxRate int) *BufferedChannel {
    return &BufferedChannel{
        ch:      make(chan *event.Event, size),
        limiter: NewRateLimiter(maxRate, size),
    }
}

func (bc *BufferedChannel) Send(evt *event.Event) {
    bc.limiter.Wait() // Block if rate exceeded
    bc.ch <- evt
}

func (bc *BufferedChannel) Receive() <-chan *event.Event {
    return bc.ch
}
```

**Milestone 4**: Multi-worker parallelism, 100K+ events/sec

---

### Phase 5: Advanced Features (Week 9-10)

#### 5.1 Kafka Integration

Create `pkg/source/kafka.go`:
```go
package source

import (
    "github.com/segmentio/kafka-go"
    "streamflow/pkg/event"
)

// KafkaSource reads from Kafka topic
type KafkaSource struct {
    reader  *kafka.Reader
    running bool
}

func NewKafkaSource(brokers []string, topic string, groupID string) *KafkaSource {
    reader := kafka.NewReader(kafka.ReaderConfig{
        Brokers: brokers,
        Topic:   topic,
        GroupID: groupID,
    })
    
    return &KafkaSource{reader: reader}
}

func (k *KafkaSource) Start(out chan<- *event.Event) error {
    k.running = true
    
    for k.running {
        msg, err := k.reader.ReadMessage(context.Background())
        if err != nil {
            return err
        }
        
        var data map[string]interface{}
        json.Unmarshal(msg.Value, &data)
        
        evt := event.NewEvent(string(msg.Key), data)
        evt.Timestamp = msg.Time.UnixMilli()
        
        out <- evt
    }
    
    close(out)
    return nil
}

func (k *KafkaSource) Stop() error {
    k.running = false
    return k.reader.Close()
}
```

#### 5.2 MiniKV Sink

Create `pkg/sink/minikv.go`:
```go
package sink

import (
    "bytes"
    "encoding/json"
    "net/http"
    "streamflow/pkg/event"
)

// MiniKVSink writes to MiniKV cluster
type MiniKVSink struct {
    gatewayURL string
    client     *http.Client
}

func NewMiniKVSink(gatewayURL string) *MiniKVSink {
    return &MiniKVSink{
        gatewayURL: gatewayURL,
        client:     &http.Client{},
    }
}

func (m *MiniKVSink) Write(evt *event.Event) error {
    // Write to MiniKV: /set/{key}
    url := m.gatewayURL + "/set/" + evt.Key
    
    jsonData, err := json.Marshal(evt.Value)
    if err != nil {
        return err
    }
    
    _, err = m.client.Post(url, "application/json", bytes.NewBuffer(jsonData))
    return err
}

func (m *MiniKVSink) Close() error {
    return nil
}
```

#### 5.3 Metrics

Create `pkg/metrics/metrics.go`:
```go
package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

var (
    EventsProcessed = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "streamflow_events_processed_total",
            Help: "Total events processed",
        },
        []string{"operator"},
    )
    
    ProcessingLatency = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "streamflow_processing_latency_seconds",
            Help:    "Event processing latency",
            Buckets: prometheus.DefBuckets,
        },
        []string{"operator"},
    )
    
    WindowSize = promauto.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "streamflow_window_size",
            Help: "Number of events in window",
        },
        []string{"window_id"},
    )
)
```

**Milestone 5**: Production features (Kafka, MiniKV, metrics)

---

### Phase 6: Production Ready (Week 11-12)

#### 6.1 Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM golang:1.21-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN go build -o streamflow ./cmd/streamflow

FROM alpine:latest
RUN apk --no-cache add ca-certificates

WORKDIR /root/
COPY --from=builder /app/streamflow .

EXPOSE 9090
CMD ["./streamflow"]
```

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  streamflow-worker1:
    build: .
    environment:
      - WORKER_ID=1
      - NUM_WORKERS=4
    ports:
      - "9091:9090"
  
  streamflow-worker2:
    build: .
    environment:
      - WORKER_ID=2
      - NUM_WORKERS=4
    ports:
      - "9092:9090"
  
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9093:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

#### 6.2 Benchmarks

Create `benchmarks/benchmark.go`:
```go
package main

import (
    "fmt"
    "streamflow/pkg/event"
    "streamflow/pkg/sink"
    "streamflow/pkg/source"
    "streamflow/pkg/stream"
    "time"
)

func main() {
    // Benchmark throughput
    fmt.Println("Running throughput benchmark...")
    
    src := source.NewGeneratorSource(100000, 10*time.Second) // 100K events/sec
    
    start := time.Now()
    processed := 0
    
    pipeline := stream.NewStream(src).
        Map(func(evt *event.Event) *event.Event {
            processed++
            return evt
        }).
        Sink(sink.NewStdoutSink())
    
    pipeline.Run()
    
    duration := time.Since(start)
    throughput := float64(processed) / duration.Seconds()
    
    fmt.Printf("Throughput: %.2f events/sec\n", throughput)
    fmt.Printf("Duration: %v\n", duration)
}
```

#### 6.3 Testing

Create `tests/integration_test.go`:
```go
package tests

import (
    "testing"
    "streamflow/pkg/event"
    "streamflow/pkg/operator"
    "streamflow/pkg/window"
)

func TestTumblingWindow(t *testing.T) {
    // Test tumbling window with 60s interval
    assigner := window.NewTumblingWindowAssigner(60 * time.Second)
    
    // Event at timestamp 0
    windows := assigner.AssignWindows(0)
    if len(windows) != 1 {
        t.Errorf("Expected 1 window, got %d", len(windows))
    }
    if windows[0].Start != 0 || windows[0].End != 60000 {
        t.Errorf("Wrong window bounds: %v", windows[0])
    }
}

func TestMapOperator(t *testing.T) {
    // Test map doubles values
    in := make(chan *event.Event, 1)
    out := make(chan *event.Event, 1)
    
    op := operator.NewMapOperator("test", func(evt *event.Event) *event.Event {
        evt.Value["doubled"] = evt.Value["value"].(int) * 2
        return evt
    })
    
    go op.Process(in, out)
    
    in <- event.NewEvent("key", map[string]interface{}{"value": 5})
    close(in)
    
    result := <-out
    if result.Value["doubled"].(int) != 10 {
        t.Errorf("Expected 10, got %d", result.Value["doubled"])
    }
}
```

**Milestone 6**: Production-ready with Docker, benchmarks, tests

---

## Example: End-to-End Pipeline

Create `examples/analytics_pipeline.go`:
```go
package main

import (
    "fmt"
    "streamflow/pkg/event"
    "streamflow/pkg/operator"
    "streamflow/pkg/sink"
    "streamflow/pkg/source"
    "streamflow/pkg/stream"
    "streamflow/pkg/window"
    "time"
)

func main() {
    // Real-time analytics: Count page views per minute
    
    src := source.NewKafkaSource(
        []string{"localhost:9092"},
        "pageviews",
        "analytics-group",
    )
    
    pipeline := stream.NewStream(src).
        // Extract page from event
        Map(func(evt *event.Event) *event.Event {
            evt.Key = evt.Value["page"].(string)
            return evt
        }).
        // Only count product pages
        Filter(func(evt *event.Event) bool {
            page := evt.Value["page"].(string)
            return strings.HasPrefix(page, "/product")
        }).
        // 60-second tumbling window
        Window(window.NewTumblingWindow(60 * time.Second)).
        // Count events per window
        Aggregate(operator.Count()).
        // Write to MiniKV
        Sink(sink.NewMiniKVSink("http://localhost:8000"))
    
    fmt.Println("Starting analytics pipeline...")
    if err := pipeline.Run(); err != nil {
        fmt.Printf("Error: %v\n", err)
    }
}
```

---

## Performance Targets

Verify with benchmarks:

| Metric | Target | How to Test |
|--------|--------|-------------|
| **Throughput** | 150K+ events/sec | `benchmark.go` with 4 workers |
| **Latency (P99)** | <50ms | Histogram in metrics |
| **Window accuracy** | ±100ms | Verify window boundaries |
| **Checkpoint time** | <1s for 1GB | Measure checkpoint duration |
| **Recovery time** | <10s | Kill process, measure restart |
| **Memory usage** | <500MB | Monitor with Prometheus |

---

## Success Criteria

✅ **Core Features**:
- Sources: Kafka, HTTP, File, Generator
- Operators: Map, Filter, FlatMap, Reduce, Aggregate
- Windows: Tumbling, Sliding, Session
- Sinks: Kafka, MiniKV, File, Stdout

✅ **Performance**:
- 150K+ events/sec with 4 workers
- P99 latency <50ms
- Handles 1M events without crashing

✅ **Fault Tolerance**:
- Checkpoints every 10s
- Recovers from crash in <10s
- Exactly-once semantics

✅ **Production**:
- Docker deployment
- Prometheus metrics
- Comprehensive tests (unit + integration)
- Documentation

---

## Resume Bullet

**StreamFlow — Distributed Real-Time Stream Processing Engine** (Mar 2026 - Jun 2026)
- Engineered real-time data processing framework in Go achieving 150,000+ events/sec throughput across 4 parallel workers with <50ms P99 latency through operator chaining and zero-copy event passing
- Implemented tumbling, sliding, and session windowing algorithms with watermark-based late event handling, enabling accurate time-based aggregations (±100ms) over unbounded data streams
- Designed fault-tolerant stateful processing using BoltDB with periodic checkpointing (10s intervals) and exactly-once semantics, achieving <8s recovery time from failures with zero data loss across 200+ chaos tests
- Built backpressure mechanism using token bucket algorithm propagating flow control from slow sinks to fast sources, preventing OOM errors under 10x load spikes while maintaining stable throughput
- Integrated with Kafka and MiniKV as sources/sinks, demonstrating end-to-end pipeline: Kafka → StreamFlow (filter/aggregate) → MiniKV serving live analytics dashboards with <2s data freshness

---

## Dependencies

Create `go.mod`:
```go
module streamflow

go 1.21

require (
    github.com/segmentio/kafka-go v0.4.45
    go.etcd.io/bbolt v1.3.8
    github.com/prometheus/client_golang v1.17.0
)
```

---

## Project Structure

```
streamflow/
├── cmd/
│   └── streamflow/
│       └── main.go              # Entry point
├── pkg/
│   ├── event/
│   │   └── event.go             # Event data model
│   ├── operator/
│   │   ├── operator.go          # Map, Filter, FlatMap
│   │   ├── windowed.go          # Windowed operators
│   │   └── stateful.go          # Stateful operators
│   ├── window/
│   │   └── window.go            # Window definitions
│   ├── source/
│   │   ├── source.go            # File, Generator
│   │   └── kafka.go             # Kafka source
│   ├── sink/
│   │   ├── sink.go              # Stdout, File
│   │   ├── kafka.go             # Kafka sink
│   │   └── minikv.go            # MiniKV sink
│   ├── stream/
│   │   └── stream.go            # Pipeline builder
│   ├── state/
│   │   └── state.go             # State management
│   ├── checkpoint/
│   │   └── checkpoint.go        # Checkpointing
│   ├── executor/
│   │   └── executor.go          # Parallel execution
│   ├── backpressure/
│   │   └── backpressure.go      # Flow control
│   └── metrics/
│       └── metrics.go           # Prometheus metrics
├── examples/
│   ├── simple_pipeline.go
│   └── analytics_pipeline.go
├── benchmarks/
│   └── benchmark.go
├── tests/
│   ├── integration_test.go
│   └── chaos_test.go
├── docker-compose.yml
├── Dockerfile
├── README.md
└── go.mod
```

---

## Documentation Requirements

### README.md Structure:
```markdown
# StreamFlow - Real-Time Stream Processing Engine

## What is StreamFlow?
[One paragraph explanation]

## Quick Start
[5-line example that works]

## Architecture
[Diagram with sources → operators → sinks]

## Core Concepts
- Events
- Operators
- Windows
- State
- Fault Tolerance

## API Reference
[Every operator with examples]

## Performance
[Benchmarks with graphs]

## Examples
- Page view analytics
- Fraud detection
- IoT aggregation

## Operations
- Deployment
- Monitoring
- Troubleshooting
```

---

## Final Notes

- **Start with basics**: Get Source → Map → Sink working first
- **Windows are hard**: Spend time understanding windowing semantics
- **Test thoroughly**: Windowing bugs are subtle
- **Benchmark early**: Performance matters in streaming
- **Document everything**: Streaming concepts need explanation

**Estimated time**: 12 weeks
**Lines of code**: ~5,000-6,000
**Complexity**: High (graduate-level distributed systems)

This is your differentiator project. Make it shine! 🚀

