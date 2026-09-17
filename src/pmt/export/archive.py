"""Bounded extraction of capture archives into a new directory."""

from pathlib import Path, PurePosixPath
import os
import shutil
import tarfile
import tempfile


def unpack_archive(source, output, max_bytes=2 * 1024 ** 3, max_files=10000):
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("output already exists: " + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".pmt-unpack-", dir=str(output.parent)))
    try:
        with tarfile.open(str(source), "r:*") as bundle:
            members = []
            names = set()
            total = 0
            for member in bundle:
                relative = PurePosixPath(member.name)
                if relative.is_absolute() or ".." in relative.parts or not relative.parts or "\\" in member.name:
                    raise ValueError("unsafe archive path: " + member.name)
                normalized = str(relative)
                if normalized in names:
                    raise ValueError("duplicate archive path: " + normalized)
                names.add(normalized)
                if not member.isdir() and not member.isfile():
                    raise ValueError("archive links and special files are not supported")
                total += member.size
                if member.size < 0 or total > max_bytes or len(names) > max_files:
                    raise ValueError("archive exceeds extraction limits")
                members.append((member, relative))
            for member, relative in members:
                target = stage.joinpath(*relative.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(member) as stream, target.open("xb") as destination:
                        shutil.copyfileobj(stream, destination, 1024 * 1024)
                    target.chmod(0o640)
        from pmt.capture import sampler
        runs = [path.parent for path in stage.rglob("run.json") if (path.parent / "snapshots").is_dir()]
        if len(runs) != 1:
            raise ValueError("archive must contain exactly one capture run")
        verification = sampler.verify_run(runs[0], write_report=False)
        if not verification["AllObservedFilesValid"] or not verification["ObservedFiles"]:
            raise ValueError("unpacked capture verification failed")
        relative_run = runs[0].relative_to(stage)
        if output.exists():
            raise FileExistsError(str(output))
        os.rename(str(stage), str(output))
        return {"output": str(output), "run_dir": str(output / relative_run), "verification": verification}
    finally:
        if stage.exists():
            shutil.rmtree(str(stage))