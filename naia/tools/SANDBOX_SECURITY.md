# Sandbox Security Model

## Current Implementation Status

**IMPORTANT: The current code execution sandbox is NOT a full security isolation boundary.**

### What IS Currently Isolated

The current sandbox implementation in `sandbox.py` provides the following protections:

1. **Temporary Directory Isolation**: Code executes in a temporary directory that is deleted after execution
2. **Workspace Path Traversal Protection**: File operations are restricted to the configured workspace root
3. **Network Isolation for URLs**: The network sandbox blocks access to private/internal IP addresses (localhost, 127.0.0.1, private ranges)
4. **Timeout Protection**: Code execution is limited to a configurable timeout (default 3 seconds)
5. **Output Truncation**: stdout/stderr are truncated to prevent memory exhaustion

### What is NOT Currently Isolated

**CRITICAL SECURITY WARNING**: The following protections are NOT currently implemented:

1. **No Process Isolation**: Python code runs with `-I` flag (isolated mode) but still runs in the same process space as the host
2. **No Network Isolation for Code Execution**: Python code can still access the network unless explicitly restricted
3. **No Resource Limits**: No CPU, memory, or disk usage limits beyond basic timeout
4. **No Containerization**: No Docker, nsjail, or chroot-based isolation
5. **No Filesystem Isolation**: While path traversal is protected, the code can still access any file within the workspace
6. **No Privilege Dropping**: Code runs with the same privileges as the NAIA process

### Recommended Production Deployment

For production use, you MUST replace the current sandbox with one of the following:

#### Option 1: Docker Container (Recommended)

```python
import docker

client = docker.from_env()
container = client.containers.run(
    "python:3.11-slim",
    command=["python", "-c", code],
    mem_limit="128m",
    cpu_quota=50000,
    network_disabled=True,
    read_only=True,
    tmpfs={"/tmp": "rw,noexec,nosuid,size=100m"},
    remove=True,
    capture_output=True,
    timeout=3,
)
```

#### Option 2: nsjail (Linux only)

```bash
nsjail \
    --mode o \
    --chroot /path/to/chroot \
    --mount proc /proc \
    --mount tmpfs /tmp:size=100m \
    --rlimit_as 134217728 \
    --rlimit_cpu 3 \
    --disable_proc \
    --network none \
    -- python -c "$code"
```

#### Option 3: Firejail (Linux only)

```bash
firejail \
    --noprofile \
    --private \
    --private-dev \
    --private-tmp \
    --nosound \
    --novideo \
    --no3d \
    --net none \
    --rlimit-as=128m \
    --seccomp \
    -- python -c "$code"
```

### Migration Path

To upgrade the sandbox:

1. **Phase 1**: Add Docker as an optional backend (fallback to current implementation)
2. **Phase 2**: Test Docker backend in staging environment
3. **Phase 3**: Make Docker the default backend
4. **Phase 4**: Remove the current subprocess-based implementation

### Current Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Code escapes workspace | Medium | High | Path traversal checks |
| Code accesses network | High | Medium | Governance approval for HIGH/CRITICAL tools |
| Code exhausts resources | Low | Medium | Timeout protection |
| Code persists malicious files | Low | High | Temporary directory cleanup |
| Code accesses host system | Low | Critical | Governance approval for CRITICAL tools |

### Governance Integration

The current implementation relies on the governance layer to mitigate risks:

- HIGH and CRITICAL risk tools require human approval
- Risk gate evaluates tool arguments for dangerous patterns
- Permission levels restrict which users can execute which tools
- All tool executions are logged for audit

### Documentation References

- Constitution Section 4: Autonomy Rules
- Constitution Section 7: Failure Philosophy
- Tools Registry: Tool definitions with risk levels
- Risk Gate: Argument validation and risk assessment
