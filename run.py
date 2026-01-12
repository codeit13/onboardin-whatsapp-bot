#!/usr/bin/env python3
"""
Production-ready FastAPI server runner with multi-worker support and Celery integration

Usage:
    python run.py                    # Run with auto-detected workers
    WORKERS=4 python run.py          # Run with 4 workers
    START_CELERY=false python run.py # Run without Celery
"""
import os
import sys
import signal
import multiprocessing
import subprocess
import time
from pathlib import Path

import uvicorn
from app.core.config import get_settings

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))


def get_worker_count() -> int:
    """
    Calculate optimal number of workers based on CPU cores.
    
    For I/O-bound applications (like FastAPI with DB/Redis):
    - Formula: (2 * num_cores) + 1 (for I/O-bound)
    - But we reserve cores for other services (Celery, DB, Redis)
    - Default: Use 75% of available cores, minimum 2, maximum 8
    
    Can be overridden via WORKERS environment variable.
    """
    settings = get_settings()
    
    # Check if explicitly set via environment variable
    workers_env = os.getenv("WORKERS") or settings.WORKERS
    if workers_env:
        try:
            return int(workers_env)
        except (ValueError, TypeError):
            pass
    
    # Auto-detect CPU cores
    cpu_count = multiprocessing.cpu_count()
    
    # For I/O-bound apps, use 75% of cores (reserve some for other services)
    # Minimum 2 workers, maximum 8 workers for stability
    workers = max(2, min(8, int(cpu_count * 0.75)))
    
    return workers


def start_celery_worker() -> subprocess.Popen | None:
    """
    Start Celery worker process
    
    Returns:
        Celery worker process or None if not started
    """
    start_celery = os.getenv("START_CELERY", "true").lower() == "true"
    
    if not start_celery:
        return None
    
    try:
        print("🔄 Starting Celery worker...")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "app.celery_app",
                "worker",
                "--loglevel=info",
                "--concurrency=4",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print(f"   ✅ Celery worker started (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"   ⚠️  Failed to start Celery worker: {e}")
        return None


def cleanup_processes(processes: dict[str, subprocess.Popen | None]) -> None:
    """Gracefully terminate all subprocesses."""
    print("\n🛑 Shutting down processes...")
    for name, process in processes.items():
        if process and process.poll() is None:  # Process is still running
            print(f"   Stopping {name}...")
            try:
                process.terminate()
                # Wait up to 5 seconds for graceful shutdown
                process.wait(timeout=5)
                print(f"   ✅ {name} stopped gracefully")
            except subprocess.TimeoutExpired:
                print(f"   ⚠️  Force killing {name}...")
                process.kill()
                process.wait()
                print(f"   ✅ {name} force killed")
            except Exception as e:
                print(f"   ❌ Error stopping {name}: {e}")


def signal_handler(signum, frame, processes: dict[str, subprocess.Popen | None]) -> None:
    """Handle shutdown signals"""
    print(f"\n⚠️  Received signal {signum}, shutting down...")
    cleanup_processes(processes)
    sys.exit(0)


if __name__ == "__main__":
    settings = get_settings()
    workers = get_worker_count()
    cpu_count = multiprocessing.cpu_count()
    
    # Check if Celery should be started
    start_celery = os.getenv("START_CELERY", "true").lower() == "true"
    
    print("=" * 60)
    print("🚀 Starting Onboarding FastAPI Server")
    print("=" * 60)
    print(f"   Environment: {settings.ENVIRONMENT}")
    print(f"   Debug Mode: {settings.DEBUG}")
    print(f"   CPU Cores: {cpu_count}")
    print(f"   Workers: {workers}")
    print(f"   Host: {settings.HOST}")
    print(f"   Port: {settings.PORT}")
    print(f"   Celery: {'Enabled' if start_celery else 'Disabled'}")
    print("=" * 60)
    
    # Track subprocesses
    processes: dict[str, subprocess.Popen | None] = {}
    
    # Register signal handlers
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, processes))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, processes))
    
    # Start Celery worker if enabled
    if start_celery:
        celery_process = start_celery_worker()
        processes["celery"] = celery_process
        
        # Give Celery a moment to start
        if celery_process:
            time.sleep(2)
    
    try:
        # Start FastAPI server
        print(f"\n🌐 FastAPI server starting...\n")
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.RELOAD,
            workers=workers if not settings.RELOAD else 1,  # Reload mode uses 1 worker
            log_level=settings.LOG_LEVEL.lower(),
        )
    except KeyboardInterrupt:
        print("\n⚠️  Keyboard interrupt received")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        raise
    finally:
        cleanup_processes(processes)
