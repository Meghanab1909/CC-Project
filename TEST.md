# Docksmith Configuration Testing Guide

This document outlines a set of configuration changes and experiments to validate the robustness of the Docksmith container system. These tests demonstrate correct handling of environment variables, caching, filesystem isolation, and configuration inheritance.

---

## 🧱 Base Setup (Already Completed)

* Imported `ubuntu:focal` base image
* Created sample app (`~/testapp`)
* Built and ran image successfully

---

## 🔧 1. CMD Override Test

### Change

```dockerfile
CMD ["/bin/sh", "-c", "echo Default CMD works"]
```

### Run

```bash
sudo python3 main.py run myapp:latest
sudo python3 main.py run myapp:latest /bin/sh -c "echo overridden"
```

### Expected

* Default CMD runs normally
* CMD can be overridden at runtime

### Purpose

Validates command override behavior (like Docker)

---

## 🌱 2. Environment Variable Handling

### Change

```dockerfile
ENV GREETING=hello
ENV TARGET=world
CMD ["/bin/sh", "-c", "echo $GREETING $TARGET"]
```

### Run

```bash
sudo python3 main.py run myapp:latest
sudo python3 main.py run -e TARGET=Docksmith myapp:latest
```

### Expected

* Default: `hello world`
* Override: `hello Docksmith`

### Purpose

Tests environment variable merging and overrides

---

## 📁 3. WORKDIR Behavior

### Case 1: Without WORKDIR

```dockerfile
CMD ["pwd"]
```

Expected output:

```
/
```

### Case 2: With WORKDIR

```dockerfile
WORKDIR /app
CMD ["pwd"]
```

Expected output:

```
/app
```

### Purpose

Ensures working directory is applied correctly

---

## 📦 4. COPY Cache Validation

### Change

```dockerfile
COPY app.py /app/
```

### Test

```bash
echo "new file" > extra.txt
# rebuild → should use cache

echo "# changed" >> app.py
# rebuild → cache miss
```

### Purpose

Validates layer caching based on file changes

---

## ⚙️ 5. Base Image Config Modification

### Edit File

```
~/.docksmith/images/ubuntu_focal.json
```

### Change

```json
"Cmd": ["/bin/echo", "hello from base"]
```

### Test

Build an image without CMD

### Purpose

Checks config inheritance from base image

---

## 🔒 6. Filesystem Isolation Test

### Run

```bash
sudo python3 main.py run myapp:latest /bin/sh -c "touch /tmp/testfile"
ls /tmp/testfile
```

### Expected

```
No such file or directory
```

### Purpose

Ensures container does not affect host filesystem

---

## 🧪 7. Invalid Configuration Handling

### Example Errors

```dockerfile
CMD invalid_json
```

```dockerfile
ENV =broken
```

### Expected

* Build should fail with proper error

### Purpose

Tests robustness against bad input

---

## 🚀 8. WORKDIR + Relative COPY

### Change

```dockerfile
WORKDIR /app
COPY . .
CMD ["ls"]
```

### Expected

* Lists files inside `/app`

### Purpose

Validates relative paths with WORKDIR

---

## 🧩 9. Multiple Image Tags

### Duplicate Base Image

```bash
cp ~/.docksmith/images/ubuntu_focal.json ~/.docksmith/images/ubuntu_test.json
```

### Modify

```json
"name": "ubuntu",
"tag": "test"
```

### Use

```dockerfile
FROM ubuntu:test
```

### Purpose

Tests image tag resolution

---

## 💥 10. Layer Ordering Test

### Original

```dockerfile
COPY . /app
RUN echo "build complete"
```

### Modified

```dockerfile
RUN echo "build complete"
COPY . /app
```

### Test

Modify a file and rebuild

### Expected

* RUN layer cached
* COPY layer invalidated

### Purpose

Validates correct layer dependency ordering

---

## 🧠 Conclusion

These tests demonstrate that Docksmith correctly handles:

* Command overrides
* Environment variables
* Working directory behavior
* Layer caching and invalidation
* Base image inheritance
* Filesystem isolation
* Error handling
* Image tagging
* Build layer ordering

---

## 🎯 Suggested Demo Strategy

For presentation:

1. Pick 3–4 tests
2. Explain:

   * What changed
   * Expected outcome
   * Actual result
   * Why it proves correctness

---

## 👥 Contributors

* Meghanab1909
* mrukudcode (Mrunal Kudtarkar)
* Rakshitha-Raksta
* mithamk

---

## 🛠 Tech Stack

* Python (100%)

---
