# Docksmith

A simplified Docker-like build and runtime system built from scratch using Linux OS primitives.

## Prerequisites
```bash
sudo apt update
sudo apt install git python3 debootstrap -y
```

## Step 1 — Clone the repo
```bash
git clone https://github.com/Meghanab1909/CC-Project.git
cd CC-Project
```

## Step 2 — Import base image (one time only)
```bash
sudo debootstrap --variant=minbase focal /tmp/base_rootfs http://archive.ubuntu.com/ubuntu

sudo tar --create --file /tmp/base_v4.tar --sort=name --mtime=1970-01-01 --numeric-owner -C /tmp/base_rootfs . && echo "tar ok"

sudo python3 - << 'PYEOF'
import os, hashlib, json, datetime, pwd
sudo_user  = os.environ.get("SUDO_USER")
home       = pwd.getpwnam(sudo_user).pw_dir if sudo_user else os.path.expanduser("~")
layers_dir = os.path.join(home, ".docksmith", "layers")
images_dir = os.path.join(home, ".docksmith", "images")
os.makedirs(layers_dir, exist_ok=True)
os.makedirs(images_dir, exist_ok=True)
with open("/tmp/base_v4.tar", "rb") as f:
    raw = f.read()
    digest = hashlib.sha256(raw).hexdigest()
dest = os.path.join(layers_dir, digest + ".tar")
with open(dest, "wb") as f:
    f.write(raw)
manifest = {
    "name": "ubuntu", "tag": "focal", "digest": "",
    "created": datetime.datetime.utcnow().isoformat(),
    "config": {"Env": [], "Cmd": ["/bin/sh"], "WorkingDir": "/"},
    "layers": [{"digest": f"sha256:{digest}", "size": os.path.getsize(dest), "createdBy": "base"}]
}
canonical = json.dumps(manifest, sort_keys=True)
manifest["digest"] = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
with open(os.path.join(images_dir, "ubuntu_focal.json"), "w") as f:
    json.dump(manifest, f, indent=2)
print(f"Imported ubuntu:focal sha256:{digest[:12]}")
PYEOF
```

## Step 3 — Create sample app
```bash
mkdir -p ~/testapp

cat > ~/testapp/Docksmithfile << 'EOF'
FROM ubuntu:focal
WORKDIR /app
ENV GREETING=hello
COPY . /app
RUN echo "build complete"
CMD ["/bin/sh", "-c", "echo $GREETING from Docksmith!"]
EOF

echo "# sample app" > ~/testapp/app.py
```

## Step 4 — Build
```bash
# Cold build — all CACHE MISS
sudo python3 main.py build -t myapp:latest ~/testapp

# Warm build — all CACHE HIT, identical digest
sudo python3 main.py build -t myapp:latest ~/testapp

# Edit a file and rebuild — COPY and RUN show CACHE MISS
echo "# changed" >> ~/testapp/app.py
sudo python3 main.py build -t myapp:latest ~/testapp
```

## Step 5 — List images
```bash
sudo python3 main.py images
```

Expected output:
```
NAME            TAG        ID           CREATED
myapp           latest     cfeb1604d7cd 2026-03-20T17:47:45.965709
ubuntu          focal      6d3033dba82e 2026-03-20T17:37:53.038824
```

## Step 6 — Run container
```bash
sudo python3 main.py run myapp:latest
```

Expected output:
```
hello from Docksmith!
```

## Step 7 — Run with env override
```bash
sudo python3 main.py run -e GREETING=world myapp:latest
```

Expected output:
```
world from Docksmith!
```

## Step 8 — Isolation test
```bash
sudo python3 main.py run myapp:latest /bin/sh -c "touch /HACKED"
ls /HACKED
```

Expected output:
```
ls: cannot access '/HACKED': No such file or directory
```

## Step 9 — Remove image
```bash
sudo python3 main.py rmi myapp:latest
```