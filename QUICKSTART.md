# 🚀 MiniKV Quick Start Guide

## For Absolute Beginners - No Experience Required!

This guide will help you run MiniKV step by step.

---

## ✅ Prerequisites

You only need **Python 3.8 or higher** installed. That's it!

Check if you have it:
```bash
python3 --version
```

---

## 📁 Step 1: Open Terminal

1. **On Mac:** Press `Cmd + Space`, type "Terminal", press Enter
2. **On Windows:** Press `Win + R`, type "cmd", press Enter
3. **On Linux:** Press `Ctrl + Alt + T`

---

## 📂 Step 2: Navigate to the Project

Copy and paste this command into your terminal:

```bash
cd "/Users/yashpatil/Desktop/SDE - 6mo/minikv"
```

Press Enter.

---

## 🎯 Step 3: Choose What to Run

### Option A: Run the Example (EASIEST - START HERE!)

This automatically demonstrates all features:

```bash
python3 example.py
```

**What you'll see:** A demo of storing, retrieving, and managing data.

---

### Option B: Interactive CLI (Like Using Redis or MongoDB)

Start the interactive shell:

```bash
python3 -m client.cli
```

**Now you can type commands:**

```bash
minikv> SET name "John Doe"
OK

minikv> SET age 30
OK

minikv> GET name
"John Doe"

minikv> KEYS
1) name
2) age

minikv> SIZE
(integer) 2

minikv> HELP
# Shows all available commands

minikv> EXIT
# Exits the CLI
```

---

### Option C: Run a Single CLI Command

Execute one command without entering interactive mode:

```bash
python3 -m client.cli --command "SET mykey myvalue"
python3 -m client.cli --command "GET mykey"
```

---

### Option D: Run Tests

Verify everything works correctly:

```bash
python3 -m tests.test_concurrency
```

**Expected:** All tests pass ✓

```bash
python3 -m tests.test_recovery
```

**Expected:** All recovery tests pass ✓

---

### Option E: Run Performance Benchmarks

See how fast MiniKV can go:

```bash
python3 -m benchmarks.benchmark
```

**Expected:** Performance statistics showing operations per second and latency.

With fewer operations (faster):
```bash
python3 -m benchmarks.benchmark --operations 1000
```

With more workers:
```bash
python3 -m benchmarks.benchmark --workers 8
```

---

## 📚 Available CLI Commands

When using the interactive CLI, you can use these commands:

| Command | What It Does | Example |
|---------|-------------|---------|
| `SET key value` | Store data | `SET name "John"` |
| `GET key` | Retrieve data | `GET name` |
| `DELETE key` | Remove data | `DELETE name` |
| `EXISTS key` | Check if key exists | `EXISTS name` |
| `KEYS` | List all keys | `KEYS` |
| `VALUES` | List all values | `VALUES` |
| `ITEMS` | List all key-value pairs | `ITEMS` |
| `SIZE` | Count entries | `SIZE` |
| `CLEAR` | Delete everything | `CLEAR` |
| `STATS` | Show system info | `STATS` |
| `HELP` | Show help | `HELP` |
| `EXIT` | Quit | `EXIT` |

---

## 💾 Where Is Data Stored?

By default, MiniKV stores data in:
- **`minikv.db`** - SQLite database file (persistent storage)
- **`minikv.wal`** - Write-Ahead Log (for crash recovery)

These files are created automatically in your project directory.

---

## 🔧 Advanced Options

### Run with Different Settings

**With 8 worker threads (more concurrency):**
```bash
python3 -m client.cli --workers 8
```

**Without persistence (in-memory only, faster):**
```bash
python3 -m client.cli --no-persistence
```

**Custom database location:**
```bash
python3 -m client.cli --db /path/to/my.db --wal /path/to/my.wal
```

---

## 🎓 Example Session

Here's a complete example session:

```bash
# 1. Start the CLI
python3 -m client.cli

# 2. Store some user data
minikv> SET user:1 {"name": "Alice", "email": "alice@example.com", "age": 30}
OK

minikv> SET user:2 {"name": "Bob", "email": "bob@example.com", "age": 25}
OK

# 3. Retrieve data
minikv> GET user:1
{
  "name": "Alice",
  "email": "alice@example.com",
  "age": 30
}

# 4. Check what's stored
minikv> KEYS
1) user:1
2) user:2

minikv> SIZE
(integer) 2

# 5. Update multiple keys at once
minikv> UPDATE {"product:1": "Laptop", "product:2": "Mouse"}
OK - Updated 2 key(s)

# 6. View statistics
minikv> STATS
{
  "running": true,
  "total_requests": 6,
  "num_workers": 4,
  "store_size": 4
}

# 7. Exit
minikv> EXIT
Goodbye!
```

---

## ❓ Troubleshooting

### "python3: command not found"
Try `python` instead of `python3`:
```bash
python example.py
```

### "No module named 'client'"
Make sure you're in the correct directory:
```bash
cd "/Users/yashpatil/Desktop/SDE - 6mo/minikv"
pwd  # Should show the minikv directory
```

### Permission denied
Add execute permissions:
```bash
chmod +x example.py
```

---

## 🎉 You're Ready!

Start with:
```bash
python3 example.py
```

Then try the interactive CLI:
```bash
python3 -m client.cli
```

**Have fun exploring MiniKV!** 🚀

For more details, see the full [README.md](README.md)

