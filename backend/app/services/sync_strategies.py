"""
Sync strategies for directory synchronization.
Uses the Strategy pattern to allow different sync algorithms.
"""
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.sql import TrackedDirectory, DirectorySnapshot, MerkleNode
from .image import scan_directory, compute_file_hash, is_image_path


@dataclass
class SyncResult:
    """Result of a directory sync operation"""
    tracked_directory_id: int
    added: List[str]
    modified: List[str]
    deleted: List[str]
    unchanged: int
    errors: List[str]
    sync_duration_seconds: float
    strategy_used: str


class SyncStrategy(ABC):
    """Abstract base class for sync strategies"""

    @abstractmethod
    async def sync(self, tracked_dir: TrackedDirectory, session: AsyncSession) -> SyncResult:
        """Synchronize a tracked directory."""
        pass

    @abstractmethod
    async def cleanup(self, tracked_dir: TrackedDirectory, session: AsyncSession) -> None:
        """Clean up strategy-specific data when a directory is removed."""
        pass


class SnapshotSyncStrategy(SyncStrategy):
    """
    Snapshot-based sync strategy.

    Tracks files by their relative path, mtime, size, and hash.
    Efficient for most use cases - uses mtime/size as quick change detection.
    """

    async def sync(self, tracked_dir: TrackedDirectory, session: AsyncSession) -> SyncResult:
        start_time = time.time()
        dir_path = Path(tracked_dir.path).expanduser().resolve()
        errors = []

        if not dir_path.exists():
            return SyncResult(
                tracked_directory_id=tracked_dir.id,
                added=[], modified=[], deleted=[],
                unchanged=0,
                errors=[f"Directory does not exist: {dir_path}"],
                sync_duration_seconds=time.time() - start_time,
                strategy_used="snapshot",
            )

        existing_snapshots = await self._load_snapshots(tracked_dir.id, session)
        current_files = await self._scan_files(dir_path)

        added, modified, unchanged, errors = self._detect_changes(
            current_files, existing_snapshots
        )
        deleted = [
            rel_path for rel_path in existing_snapshots
            if rel_path not in current_files
        ]

        await self._update_snapshots(
            session, tracked_dir, added, modified, deleted, current_files
        )

        tracked_dir.last_synced_at = datetime.now(timezone.utc)
        tracked_dir.last_error = None
        await session.commit()

        return SyncResult(
            tracked_directory_id=tracked_dir.id,
            added=[str(p) for p in added],
            modified=[str(p) for p in modified],
            deleted=deleted,
            unchanged=unchanged,
            errors=errors,
            sync_duration_seconds=time.time() - start_time,
            strategy_used="snapshot",
        )

    async def _load_snapshots(
        self, tracked_dir_id: int, session: AsyncSession
    ) -> Dict[str, DirectorySnapshot]:
        result = await session.execute(
            select(DirectorySnapshot).where(
                DirectorySnapshot.tracked_directory_id == tracked_dir_id
            )
        )
        return {s.relative_path: s for s in result.scalars().all()}

    async def _scan_files(self, dir_path: Path) -> Dict[str, dict]:
        current_files = {}
        for img_path in scan_directory(dir_path):
            try:
                stat = img_path.stat()
                relative_path = str(img_path.relative_to(dir_path))
                current_files[relative_path] = {
                    "path": img_path,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
            except OSError:
                pass
        return current_files

    def _detect_changes(
        self,
        current_files: Dict[str, dict],
        existing_snapshots: Dict[str, DirectorySnapshot],
    ) -> tuple[list[Path], list[Path], int, list[str]]:
        added = []
        modified = []
        unchanged = 0
        errors = []

        for relative_path, file_info in current_files.items():
            existing = existing_snapshots.get(relative_path)

            if existing is None:
                added.append(file_info["path"])
            elif (
                existing.file_size != file_info["size"]
                or existing.modified_time != file_info["mtime"]
            ):
                file_hash = compute_file_hash(file_info["path"])
                if existing.file_hash != file_hash:
                    modified.append(file_info["path"])
                else:
                    existing.modified_time = file_info["mtime"]
                    unchanged += 1
            else:
                unchanged += 1

        return added, modified, unchanged, errors

    async def _update_snapshots(
        self,
        session: AsyncSession,
        tracked_dir: TrackedDirectory,
        added: list[Path],
        modified: list[Path],
        deleted: list[str],
        current_files: Dict[str, dict],
    ) -> None:
        dir_path = Path(tracked_dir.path).expanduser().resolve()
        now = datetime.now(timezone.utc)

        for img_path in added + modified:
            try:
                file_hash = compute_file_hash(img_path)
                stat = img_path.stat()
                relative_path = str(img_path.relative_to(dir_path))

                existing = (
                    await session.execute(
                        select(DirectorySnapshot).where(
                            DirectorySnapshot.tracked_directory_id == tracked_dir.id,
                            DirectorySnapshot.relative_path == relative_path,
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    existing.file_hash = file_hash
                    existing.file_size = stat.st_size
                    existing.modified_time = stat.st_mtime
                    existing.last_seen_at = now
                else:
                    session.add(
                        DirectorySnapshot(
                            tracked_directory_id=tracked_dir.id,
                            relative_path=relative_path,
                            file_hash=file_hash,
                            file_size=stat.st_size,
                            modified_time=stat.st_mtime,
                            last_seen_at=now,
                        )
                    )
            except OSError as e:
                pass

        if deleted:
            await session.execute(
                delete(DirectorySnapshot).where(
                    DirectorySnapshot.tracked_directory_id == tracked_dir.id,
                    DirectorySnapshot.relative_path.in_(deleted),
                )
            )

    async def cleanup(self, tracked_dir: TrackedDirectory, session: AsyncSession) -> None:
        await session.execute(
            delete(DirectorySnapshot).where(
                DirectorySnapshot.tracked_directory_id == tracked_dir.id
            )
        )
        await session.commit()


class MerkleSyncStrategy(SyncStrategy):
    """
    Merkle tree-based sync strategy.

    Builds a hash tree where:
    - File nodes: hash of file content
    - Directory nodes: hash of sorted child node hashes

    Enables efficient change detection by comparing root hashes first,
    then traversing down to changed subtrees only.
    """

    @staticmethod
    def _hash_content(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _hash_children(child_hashes: List[str]) -> str:
        sorted_hashes = sorted(child_hashes)
        combined = ",".join(sorted_hashes).encode()
        return hashlib.sha256(combined).hexdigest()

    async def _build_merkle_tree(
        self,
        dir_path: Path,
        relative_path: str = "",
        tracked_dir_id: int = 0,
        parent_id: Optional[int] = None,
    ) -> tuple[str, list[dict]]:
        node_data_list = []
        child_hashes = []

        try:
            items = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        except PermissionError:
            return "", node_data_list

        for item in items:
            item_relative = f"{relative_path}/{item.name}" if relative_path else item.name

            if item.is_dir():
                subtree_hash, subtree_nodes = await self._build_merkle_tree(
                    item, item_relative, tracked_dir_id, None
                )
                if subtree_hash:
                    child_hashes.append(subtree_hash)
                    node_data_list.extend(subtree_nodes)
            elif is_image_path(item):
                try:
                    file_hash = compute_file_hash(item)
                    stat = item.stat()

                    node_data_list.append({
                        "tracked_directory_id": tracked_dir_id,
                        "node_hash": file_hash,
                        "node_type": "file",
                        "relative_path": item_relative,
                        "parent_id": parent_id,
                        "file_hash": file_hash,
                        "file_size": stat.st_size,
                    })
                    child_hashes.append(file_hash)
                except OSError:
                    pass

        dir_hash = self._hash_children(child_hashes) if child_hashes else ""

        if dir_hash:
            node_data_list.append({
                "tracked_directory_id": tracked_dir_id,
                "node_hash": dir_hash,
                "node_type": "directory",
                "relative_path": relative_path or ".",
                "parent_id": parent_id,
                "file_hash": None,
                "file_size": None,
            })

        return dir_hash, node_data_list

    async def _load_existing_tree(
        self, tracked_dir_id: int, session: AsyncSession
    ) -> Dict[str, MerkleNode]:
        result = await session.execute(
            select(MerkleNode).where(
                MerkleNode.tracked_directory_id == tracked_dir_id
            )
        )
        return {node.relative_path: node for node in result.scalars().all()}

    async def _compare_trees(
        self,
        dir_path: Path,
        existing_tree: Dict[str, MerkleNode],
    ) -> tuple[list[Path], list[str]]:
        added = []
        deleted = []

        def traverse(current_dir: Path, relative_path: str = "") -> str:
            child_hashes = []

            try:
                items = sorted(current_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except PermissionError:
                return ""

            seen_paths = set()

            for item in items:
                item_relative = f"{relative_path}/{item.name}" if relative_path else item.name
                seen_paths.add(item_relative)

                if item.is_dir():
                    child_hash = traverse(item, item_relative)
                    if child_hash:
                        child_hashes.append(child_hash)
                elif is_image_path(item):
                    existing_node = existing_tree.get(item_relative)
                    file_hash = compute_file_hash(item)

                    if existing_node is None or existing_node.node_hash != file_hash:
                        added.append(item)
                    child_hashes.append(file_hash)

            for existing_path in existing_tree:
                if existing_path.startswith(relative_path or ".") and existing_path not in seen_paths:
                    deleted.append(existing_path)

            return self._hash_children(child_hashes) if child_hashes else ""

        traverse(dir_path)
        return added, deleted

    async def sync(self, tracked_dir: TrackedDirectory, session: AsyncSession) -> SyncResult:
        start_time = time.time()
        dir_path = Path(tracked_dir.path).expanduser().resolve()
        errors = []

        if not dir_path.exists():
            return SyncResult(
                tracked_directory_id=tracked_dir.id,
                added=[], modified=[], deleted=[],
                unchanged=0,
                errors=[f"Directory does not exist: {dir_path}"],
                sync_duration_seconds=time.time() - start_time,
                strategy_used="merkle",
            )

        try:
            existing_tree = await self._load_existing_tree(tracked_dir.id, session)

            if not existing_tree:
                return await self._initial_sync(tracked_dir, dir_path, session, start_time)

            added, deleted = await self._compare_trees(dir_path, existing_tree)
            await self._rebuild_tree(tracked_dir, dir_path, session)

            tracked_dir.last_synced_at = datetime.now(timezone.utc)
            tracked_dir.last_error = None
            await session.commit()

            return SyncResult(
                tracked_directory_id=tracked_dir.id,
                added=[str(p) for p in added],
                modified=[],
                deleted=deleted,
                unchanged=0,
                errors=errors,
                sync_duration_seconds=time.time() - start_time,
                strategy_used="merkle",
            )

        except Exception as e:
            return SyncResult(
                tracked_directory_id=tracked_dir.id,
                added=[], modified=[], deleted=[],
                unchanged=0,
                errors=[f"{type(e).__name__}: {e}"],
                sync_duration_seconds=time.time() - start_time,
                strategy_used="merkle",
            )

    async def _initial_sync(
        self,
        tracked_dir: TrackedDirectory,
        dir_path: Path,
        session: AsyncSession,
        start_time: float,
    ) -> SyncResult:
        root_hash, node_data_list = await self._build_merkle_tree(
            dir_path, "", tracked_dir.id
        )

        for node_data in node_data_list:
            session.add(MerkleNode(**node_data))

        await session.commit()

        added = [
            str(dir_path / n["relative_path"])
            for n in node_data_list
            if n["node_type"] == "file"
        ]

        return SyncResult(
            tracked_directory_id=tracked_dir.id,
            added=added,
            modified=[],
            deleted=[],
            unchanged=0,
            errors=[],
            sync_duration_seconds=time.time() - start_time,
            strategy_used="merkle",
        )

    async def _rebuild_tree(
        self,
        tracked_dir: TrackedDirectory,
        dir_path: Path,
        session: AsyncSession,
    ) -> None:
        await session.execute(
            delete(MerkleNode).where(
                MerkleNode.tracked_directory_id == tracked_dir.id
            )
        )

        root_hash, node_data_list = await self._build_merkle_tree(
            dir_path, "", tracked_dir.id
        )

        for node_data in node_data_list:
            session.add(MerkleNode(**node_data))

        await session.commit()

    async def cleanup(self, tracked_dir: TrackedDirectory, session: AsyncSession) -> None:
        await session.execute(
            delete(MerkleNode).where(
                MerkleNode.tracked_directory_id == tracked_dir.id
            )
        )
        await session.commit()


def get_sync_strategy(strategy_name: str) -> SyncStrategy:
    """Get sync strategy instance by name"""
    strategies = {
        "snapshot": SnapshotSyncStrategy(),
        "merkle": MerkleSyncStrategy(),
    }
    if strategy_name not in strategies:
        raise ValueError(
            f"Unknown sync strategy: {strategy_name}. "
            f"Available: {list(strategies.keys())}"
        )
    return strategies[strategy_name]
