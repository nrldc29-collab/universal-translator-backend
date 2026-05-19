"""
Audit log cleanup and retention management.

This module provides functionality for managing audit log cleanup and retention policies,
including deletion of old logs, rotation of large log files, and statistics reporting.

The cleanup manager supports:
- Configurable retention periods for audit logs
- Automatic rotation of log files exceeding size limits
- Comprehensive cleanup statistics and reporting
- Environment variable configuration for retention policies

Environment Variables:
    AUDIT_LOG_RETENTION_DAYS: Number of days to retain audit logs (default: 90)
    AUDIT_LOG_MAX_SIZE_MB: Maximum file size in MB before rotation (default: 100)
    AUDIT_LOG_DIR: Directory containing audit log files (default: logs)

Example:
    from stt_server.audit_cleanup import get_audit_cleanup

    cleanup = get_audit_cleanup()
    stats = cleanup.cleanup_and_rotate()
    print(f"Deleted {stats['cleanup']['files_deleted']} files")
"""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AuditLogCleanup:
    """
    Manage audit log cleanup and retention policies.
    
    This class handles the lifecycle management of audit log files, including
    cleanup of expired logs, rotation of oversized files, and statistics reporting.
    
    Attributes:
        retention_days: Number of days to retain audit logs before deletion
        max_file_size_mb: Maximum file size in MB before triggering rotation
        audit_log_dir: Directory path containing audit log files
        admin_audit_log_path: Path to the main admin audit log file
    """
    
    def __init__(
        self,
        retention_days: int = 90,
        max_file_size_mb: int = 100,
        audit_log_dir: Optional[str] = None,
    ):
        """
        Initialize the audit log cleanup manager.
        
        Args:
            retention_days: Number of days to retain audit logs (default: 90)
            max_file_size_mb: Maximum file size in MB before rotation (default: 100)
            audit_log_dir: Directory containing audit logs (default: logs)
        """
        self.retention_days = retention_days
        self.max_file_size_mb = max_file_size_mb
        self.audit_log_dir = Path(audit_log_dir) if audit_log_dir else Path("logs")
        self.admin_audit_log_path = self.audit_log_dir / "admin-audit.jsonl"
        logger.info(
            f"Initialized AuditLogCleanup: retention_days={retention_days}, "
            f"max_file_size_mb={max_file_size_mb}, dir={self.audit_log_dir}"
        )
    
    def cleanup_old_logs(self) -> dict:
        """
        Clean up audit logs older than retention period.
        
        Scans the audit log directory for JSONL files older than the configured
        retention period and deletes them, freeing disk space.
        
        Returns:
            Dictionary with cleanup statistics including files processed, bytes freed,
            and files deleted
        """
        logger.info(f"Starting audit log cleanup with retention_days={self.retention_days}")
        
        if not self.audit_log_dir.exists():
            logger.warning(f"Audit log directory does not exist: {self.audit_log_dir}")
            return {
                "files_processed": 0,
                "bytes_freed": 0,
                "files_deleted": 0,
            }
        
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        files_deleted = 0
        bytes_freed = 0
        files_processed = 0
        
        # Process all JSONL log files
        for log_file in self.audit_log_dir.glob("*.jsonl"):
            files_processed += 1
            
            try:
                # Check file age
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                
                if file_mtime < cutoff_date:
                    # Delete old file
                    file_size = log_file.stat().st_size
                    log_file.unlink()
                    files_deleted += 1
                    bytes_freed += file_size
                    logger.info(f"Deleted old audit log: {log_file.name} ({file_size} bytes)")
                    
            except Exception as e:
                # Log error but continue processing
                logger.error(f"Error processing {log_file}: {e}")
        
        logger.info(
            f"Audit log cleanup completed: processed={files_processed}, "
            f"deleted={files_deleted}, freed={bytes_freed} bytes"
        )
        
        return {
            "files_processed": files_processed,
            "bytes_freed": bytes_freed,
            "files_deleted": files_deleted,
            "retention_days": self.retention_days,
        }
    
    def rotate_large_logs(self) -> dict:
        """
        Rotate log files that exceed max size.
        
        Checks the main admin audit log file and rotates it if it exceeds the
        configured maximum size. Rotation renames the file with a timestamp
        and creates a new empty file for continued logging.
        
        Returns:
            Dictionary with rotation statistics including files rotated and bytes processed
        """
        logger.info(f"Checking for log rotation, max_file_size_mb={self.max_file_size_mb}")
        
        if not self.admin_audit_log_path.exists():
            logger.warning(f"Admin audit log does not exist: {self.admin_audit_log_path}")
            return {
                "files_rotated": 0,
                "bytes_processed": 0,
            }
        
        files_rotated = 0
        bytes_processed = 0
        
        try:
            file_size = self.admin_audit_log_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size_mb > self.max_file_size_mb:
                # Rotate the file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                rotated_path = self.audit_log_dir / f"admin-audit-{timestamp}.jsonl"
                
                logger.info(
                    f"Rotating audit log: {self.admin_audit_log_path.name} "
                    f"({file_size_mb:.2f} MB) -> {rotated_path.name}"
                )
                
                # Move current file to rotated name
                self.admin_audit_log_path.rename(rotated_path)
                
                files_rotated += 1
                bytes_processed += file_size
                
                # Create new empty file
                self.admin_audit_log_path.touch()
                logger.info(f"Created new empty audit log: {self.admin_audit_log_path.name}")
            else:
                logger.debug(f"Log file size {file_size_mb:.2f} MB below threshold")
                
        except Exception as e:
            logger.error(f"Error rotating log file: {e}")
        
        return {
            "files_rotated": files_rotated,
            "bytes_processed": bytes_processed,
            "max_file_size_mb": self.max_file_size_mb,
        }
    
    def cleanup_and_rotate(self) -> dict:
        """
        Perform both cleanup and rotation.
        
        Runs the full cleanup and rotation process, combining statistics from
        both operations into a single report.
        
        Returns:
            Combined statistics dictionary with cleanup and rotation results
        """
        logger.info("Starting full audit log cleanup and rotation")
        cleanup_stats = self.cleanup_old_logs()
        rotate_stats = self.rotate_large_logs()
        
        result = {
            "cleanup": cleanup_stats,
            "rotation": rotate_stats,
            "timestamp": datetime.now().isoformat(),
        }
        
        logger.info(f"Full cleanup and rotation completed: {result}")
        return result
    
    def get_log_stats(self) -> dict:
        """
        Get statistics about audit logs.
        
        Calculates comprehensive statistics about the audit log directory,
        including file counts, total size, and age information.
        
        Returns:
            Dictionary containing log directory statistics
        """
        logger.debug(f"Collecting audit log statistics for {self.audit_log_dir}")
        
        if not self.audit_log_dir.exists():
            logger.warning(f"Audit log directory does not exist: {self.audit_log_dir}")
            return {
                "log_dir_exists": False,
                "total_files": 0,
                "total_size_bytes": 0,
            }
        
        total_files = 0
        total_size = 0
        oldest_file = None
        newest_file = None
        
        for log_file in self.audit_log_dir.glob("*.jsonl"):
            total_files += 1
            file_size = log_file.stat().st_size
            total_size += file_size
            
            file_mtime = log_file.stat().st_mtime
            
            if oldest_file is None or file_mtime < oldest_file:
                oldest_file = file_mtime
            
            if newest_file is None or file_mtime > newest_file:
                newest_file = file_mtime
        
        stats = {
            "log_dir_exists": True,
            "log_dir_path": str(self.audit_log_dir),
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest_file": datetime.fromtimestamp(oldest_file).isoformat() if oldest_file else None,
            "newest_file": datetime.fromtimestamp(newest_file).isoformat() if newest_file else None,
            "retention_days": self.retention_days,
            "max_file_size_mb": self.max_file_size_mb,
        }
        
        logger.debug(f"Audit log statistics: {stats}")
        return stats


# Global cleanup instance
_global_cleanup: Optional[AuditLogCleanup] = None


def get_audit_cleanup() -> AuditLogCleanup:
    """
    Get the global audit log cleanup instance.
    
    Creates and returns a singleton instance of the audit log cleanup manager,
    configured via environment variables.
    
    Environment Variables:
        AUDIT_LOG_RETENTION_DAYS: Retention period in days (default: 90)
        AUDIT_LOG_MAX_SIZE_MB: Max file size in MB (default: 100)
        AUDIT_LOG_DIR: Audit log directory (default: logs)
        
    Returns:
        The global AuditLogCleanup instance
    """
    global _global_cleanup
    
    if _global_cleanup is None:
        retention_days = int(os.environ.get("AUDIT_LOG_RETENTION_DAYS", "90"))
        max_file_size_mb = int(os.environ.get("AUDIT_LOG_MAX_SIZE_MB", "100"))
        audit_log_dir = os.environ.get("AUDIT_LOG_DIR", "logs")
        
        _global_cleanup = AuditLogCleanup(
            retention_days=retention_days,
            max_file_size_mb=max_file_size_mb,
            audit_log_dir=audit_log_dir,
        )
        logger.info("Created global audit log cleanup instance")
    
    return _global_cleanup


async def run_scheduled_cleanup() -> None:
    """
    Run scheduled audit log cleanup.
    
    This function is typically called by a background task or scheduler to
    perform periodic audit log cleanup and rotation. Logs the results of
    the cleanup operation.
    """
    logger.info("Starting scheduled audit log cleanup")
    cleanup = get_audit_cleanup()
    stats = cleanup.cleanup_and_rotate()
    
    # Log the cleanup results
    logger.info(f"Audit log cleanup completed: {stats}")
