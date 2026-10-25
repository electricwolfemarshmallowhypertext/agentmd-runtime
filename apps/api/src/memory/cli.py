"""
Memory Management CLI
Created: 2025-11-02 19:51:19
Author: electricwolfemarshmallowhypertext
"""

import os
import sys
import click
import json
from pathlib import Path
from datetime import datetime, timedelta
import shutil
import sqlite3
import structlog
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn
from .memory_engine import MemoryEngine
from .exceptions import MemoryException

# Configure logging
logger = structlog.get_logger("sticky.memory.cli")
console = Console()

@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Memory management command line interface"""
    pass

@cli.command()
@click.option("--older-than", type=str, help="Clean memories older than (e.g. 30d, 24h)")
@click.option("--user-id", type=str, help="Clean specific user's memories")
@click.option("--force", is_flag=True, help="Skip confirmation")
def cleanup(older_than: str, user_id: str, force: bool):
    """Clean up old memories"""
    try:
        if not force:
            if not click.confirm("Are you sure you want to clean up memories?"):
                return
        
        engine = MemoryEngine(
            persist_dir=os.getenv("CHROMA_PERSIST_DIR", "memory_store"),
            sqlite_fallback_path=os.getenv("SQLITE_FALLBACK_PATH", "memory_store/fallback.db")
        )
        
        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            console=console
        ) as progress:
            task = progress.add_task("Cleaning up memories...", total=None)
            
            # Parse time delta
            if older_than:
                unit = older_than[-1]
                value = int(older_than[:-1])
                if unit == 'd':
                    delta = timedelta(days=value)
                elif unit == 'h':
                    delta = timedelta(hours=value)
                else:
                    raise ValueError("Invalid time format. Use 30d or 24h")
                cutoff = datetime.utcnow() - delta
            else:
                cutoff = None
            
            # Cleanup vector store
            deleted = engine.client.delete(
                where={
                    "$and": [
                        {"created_at": {"$lt": cutoff.isoformat()}} if cutoff else {},
                        {"user_id": user_id} if user_id else {}
                    ]
                }
            )
            
            # Cleanup SQLite
            if engine.sqlite_conn:
                cursor = engine.sqlite_conn.cursor()
                where_clause = []
                params = []
                
                if cutoff:
                    where_clause.append("created_at < ?")
                    params.append(cutoff.isoformat())
                if user_id:
                    where_clause.append("user_id = ?")
                    params.append(user_id)
                    
                where_str = " AND ".join(where_clause) if where_clause else "1=1"
                
                cursor.execute(f"DELETE FROM memories WHERE {where_str}", params)
                engine.sqlite_conn.commit()
                
            progress.update(task, completed=100)
            
        console.print(f"Cleaned up {deleted} memories")
        
    except Exception as e:
        logger.error("Cleanup failed", error=str(e))
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)

@cli.command()
@click.option("--source", type=click.Path(exists=True), help="Source directory")
@click.option("--dest", type=click.Path(), help="Destination directory")
@click.option("--retention", type=int, default=5, help="Number of backups to keep")
def backup(source: str, dest: str, retention: int):
    """Create memory store backup"""
    try:
        source_path = Path(source or os.getenv("CHROMA_PERSIST_DIR", "memory_store"))
        dest_path = Path(dest or os.getenv("MEMORY_BACKUP_DIR", "memory_store/backups"))
        
        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            console=console
        ) as progress:
            task = progress.add_task("Creating backup...", total=None)
            
            # Create backup
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = dest_path / f"memory_store_{timestamp}"
            
            # Backup Chroma
            shutil.copytree(source_path, backup_path)
            
            # Backup SQLite
            sqlite_path = source_path / "fallback.db"
            if sqlite_path.exists():
                shutil.copy2(sqlite_path, backup_path / "fallback.db")
            
            # Cleanup old backups
            backups = sorted(dest_path.glob("memory_store_*"))
            for backup in backups[:-retention]:
                shutil.rmtree(backup)
                
            progress.update(task, completed=100)
            
        console.print(f"Backup created at {backup_path}")
        
    except Exception as e:
        logger.error("Backup failed", error=str(e))
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)

@cli.command()
@click.option("--backup-path", type=click.Path(exists=True), required=True, help="Backup to restore")
@click.option("--force", is_flag=True, help="Skip confirmation")
def restore(backup_path: str, force: bool):
    """Restore from backup"""
    try:
        if not force:
            if not click.confirm("This will overwrite existing data. Continue?"):
                return
                
        dest_path = Path(os.getenv("CHROMA_PERSIST_DIR", "memory_store"))
        
        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            console=console
        ) as progress:
            task = progress.add_task("Restoring from backup...", total=None)
            
            # Clear destination
            if dest_path.exists():
                shutil.rmtree(dest_path)
            
            # Restore files
            shutil.copytree(backup_path, dest_path)
            
            progress.update(task, completed=100)
            
        console.print(f"Restored from {backup_path}")
        
    except Exception as e:
        logger.error("Restore failed", error=str(e))
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)

@cli.command()
@click.option("--user-id", type=str, help="Show specific user's stats")
def stats(user_id: str):
    """Show memory store statistics"""
    try:
        engine = MemoryEngine(
            persist_dir=os.getenv("CHROMA_PERSIST_DIR", "memory_store"),
            sqlite_fallback_path=os.getenv("SQLITE_FALLBACK_PATH", "memory_store/fallback.db")
        )
        
        # Get stats from vector store
        where_filter = {"user_id": user_id} if user_id else {}
        results = engine.client.get(
            where=where_filter,
            include=["metadatas"]
        )
        
        # Calculate stats
        total_memories = len(results["ids"])
        total_size = sum(
            len(json.dumps(meta).encode())
            for meta in results["metadatas"]
        )
        
        # Get SQLite stats
        sqlite_memories = 0
        sqlite_size = 0
        if engine.sqlite_conn:
            cursor = engine.sqlite_conn.cursor()
            where_clause = "WHERE user_id = ?" if user_id else ""
            params = [user_id] if user_id else []
            
            cursor.execute(f"SELECT COUNT(*) FROM memories {where_clause}", params)
            sqlite_memories = cursor.fetchone()[0]
            
            if engine.sqlite_path.exists():
                sqlite_size = engine.sqlite_path.stat().st_size
        
        # Display stats table
        table = Table(title="Memory Store Statistics")
        table.add_column("Metric")
        table.add_column("Value")
        
        table.add_row("Total Memories", str(total_memories))
        table.add_row("Vector Store Size", f"{total_size / 1024 / 1024:.2f} MB")
        table.add_row("SQLite Memories", str(sqlite_memories))
        table.add_row("SQLite Size", f"{sqlite_size / 1024 / 1024:.2f} MB")
        
        console.print(table)
        
    except Exception as e:
        logger.error("Stats failed", error=str(e))
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)

@cli.command()
def vacuum():
    """Vacuum SQLite database"""
    try:
        engine = MemoryEngine(
            persist_dir=os.getenv("CHROMA_PERSIST_DIR", "memory_store"),
            sqlite_fallback_path=os.getenv("SQLITE_FALLBACK_PATH", "memory_store/fallback.db")
        )
        
        if not engine.sqlite_conn:
            console.print("No SQLite database found")
            return
            
        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            console=console
        ) as progress:
            task = progress.add_task("Vacuuming database...", total=None)
            
            # Get size before
            size_before = engine.sqlite_path.stat().st_size
            
            # Vacuum database
            engine.sqlite_conn.execute("VACUUM")
            
            # Get size after
            size_after = engine.sqlite_path.stat().st_size
            
            progress.update(task, completed=100)
            
        savings = size_before - size_after
        console.print(f"Freed {savings / 1024 / 1024:.2f} MB")
        
    except Exception as e:
        logger.error("Vacuum failed", error=str(e))
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)

@cli.command()
@click.option("--user-id", type=str, required=True, help="User ID to export")
@click.option("--output", type=click.Path(), required=True, help="Output file")
def export(user_id: str, output: str):
    """Export user memories"""
    try:
        engine = MemoryEngine(
            persist_dir=os.getenv("CHROMA_PERSIST_DIR", "memory_store"),
            sqlite_fallback_path=os.getenv("SQLITE_FALLBACK_PATH", "memory_store/fallback.db")
        )
        
        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            console=console
        ) as progress:
            task = progress.add_task("Exporting memories...", total=None)
            
            # Get memories from vector store
            results = engine.client.get(
                where={"user_id": user_id},
                include=["metadatas", "embeddings"]
            )
            
            memories = []
            for meta, embedding in zip(results["metadatas"], results["embeddings"]):
                memory = json.loads(meta["memory"])
                memory["embedding"] = embedding
                memories.append(memory)
                
            # Get memories from SQLite
            if engine.sqlite_conn:
                cursor = engine.sqlite_conn.cursor()
                cursor.execute(
                    "SELECT metadata, embedding FROM memories WHERE user_id = ?",
                    [user_id]
                )
                for row in cursor:
                    memory = json.loads(row[0])
                    memory["embedding"] = list(row[1])
                    memories.append(memory)
            
            # Save to file
            with open(output, "w") as f:
                json.dump(memories, f, indent=2)
                
            progress.update(task, completed=100)
            
        console.print(f"Exported {len(memories)} memories to {output}")
        
    except Exception as e:
        logger.error("Export failed", error=str(e))
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    cli()