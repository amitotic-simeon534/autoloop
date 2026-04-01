"""
CLI for autoloop — history, best, diff, rollback.
"""

import click
import json
from pathlib import Path


@click.group()
def cli():
    """autoloop — autoresearch for everything."""
    pass


@cli.command()
@click.option("--results-dir", default="./autoloop-results", help="Results directory")
def history(results_dir):
    """Show experiment history."""
    log_path = Path(results_dir) / "experiments.jsonl"
    if not log_path.exists():
        click.echo("No experiments yet. Run autoloop first.")
        return

    experiments = [json.loads(l) for l in log_path.read_text().strip().split("\n") if l]
    click.echo(f"\n{'ID':>4} {'Score':>8} {'Delta':>8} {'Status':>10}  Description")
    click.echo("-" * 70)
    for e in experiments:
        status = "✅ KEPT" if e["improved"] else "❌ DISC"
        delta = f"+{e['delta']:.4f}" if e["delta"] >= 0 else f"{e['delta']:.4f}"
        click.echo(f"{e['experiment_id']:>4} {e['score']:>8.4f} {delta:>8} {status:>10}  {e['description'][:40]}")


@cli.command()
@click.option("--results-dir", default="./autoloop-results", help="Results directory")
def best(results_dir):
    """Show the best-performing version."""
    best_dir = Path(results_dir) / "best"
    if not best_dir.exists():
        click.echo("No best result yet.")
        return
    for f in best_dir.iterdir():
        click.echo(f"\n{'='*50}")
        click.echo(f"Best version: {f}")
        click.echo('='*50)
        click.echo(f.read_text())


@cli.command()
@click.argument("target")
@click.option("--results-dir", default="./autoloop-results", help="Results directory")
def rollback(target, results_dir):
    """Rollback to best version."""
    import shutil
    best_dir = Path(results_dir) / "best"
    best_file = best_dir / Path(target).name
    if not best_file.exists():
        click.echo(f"No best version found for {target}")
        return
    shutil.copy(best_file, target)
    click.echo(f"✅ Rolled back {target} to best version.")


def main():
    cli()


if __name__ == "__main__":
    main()
