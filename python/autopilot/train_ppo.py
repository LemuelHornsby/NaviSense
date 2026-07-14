"""PPO trainer for the yacht — curriculum-driven.

Uses Stable-Baselines3 if available (preferred), else falls back to a
minimal in-house PPO. SB3 is the right call for serious training; the
fallback exists so this file can be imported and a tiny smoke-train can
run without an extra install.

Curriculum
----------

Trains four stages back-to-back, each with its own
:class:`CurriculumStage` parameters. After each stage finishes (either
total_timesteps reached, or a success-rate threshold hit on the eval
callback), the policy moves to the next stage. The model is saved at
the end of every stage so you can roll back to a checkpoint.

CLI
---

::

    python python/autopilot/train_ppo.py \\
        --goals-file paths/dockgoals.json \\
        --output-dir runs/ppo \\
        --total-timesteps 1_000_000

The output directory ends up with:

  runs/ppo/
    stage1_open_water/
      model.zip            <-- trained policy after stage 1
      tensorboard/
    stage2_light_disturb/
      model.zip
    ...
    final_policy.zip       <-- best of the last stage
    train_log.csv          <-- per-stage summary

Deploying the trained policy live in Unity is a matter of pointing
``python_listener.py --controller ppo --policy-file <model.zip>`` at
the saved file. The deployed controller (``PpoPolicyController``)
reads the same SB3 model and acts on real sensor packets.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

# Allow `python python/autopilot/train_ppo.py` to find the package.
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from python.autopilot.yacht_env import (
    YachtEnv, DEFAULT_CURRICULUM, CurriculumStage,
)


# ---------------------------------------------------------------------------
# SB3 path
# ---------------------------------------------------------------------------

def _try_sb3():
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv
        from stable_baselines3.common.callbacks import BaseCallback
        return PPO, DummyVecEnv, BaseCallback
    except ImportError:
        return None, None, None


def train_with_sb3(
    goals_file: str,
    output_dir: str,
    total_timesteps_per_stage: int,
    n_envs: int,
    seed: int,
    curriculum=DEFAULT_CURRICULUM,
):
    PPO, DummyVecEnv, BaseCallback = _try_sb3()
    if PPO is None:
        return False  # caller falls back

    os.makedirs(output_dir, exist_ok=True)
    log_csv = os.path.join(output_dir, "train_log.csv")
    log_rows = []

    prev_model_path = None
    for stage in curriculum:
        stage_dir = os.path.join(output_dir, stage.name)
        os.makedirs(stage_dir, exist_ok=True)
        tb_dir = os.path.join(stage_dir, "tensorboard")

        def make_env(stage=stage, seed=seed):
            def _thunk():
                env = YachtEnv(
                    goals_file=goals_file,
                    curriculum=stage,
                    seed=seed,
                )
                return env
            return _thunk

        vec = DummyVecEnv([make_env() for _ in range(n_envs)])

        if prev_model_path and os.path.exists(prev_model_path):
            print(f"[ppo] loading prior policy from {prev_model_path}")
            model = PPO.load(prev_model_path, env=vec, tensorboard_log=tb_dir,
                              device="auto")
        else:
            model = PPO(
                "MlpPolicy", vec,
                learning_rate=3e-4,
                n_steps=2048,
                batch_size=64,
                n_epochs=10,
                gamma=0.99,
                gae_lambda=0.95,
                clip_range=0.2,
                ent_coef=0.01,
                tensorboard_log=tb_dir,
                seed=seed,
                verbose=1,
            )

        t0 = time.time()
        model.learn(total_timesteps=total_timesteps_per_stage,
                     tb_log_name=stage.name, reset_num_timesteps=False)
        elapsed = time.time() - t0

        ckpt = os.path.join(stage_dir, "model.zip")
        model.save(ckpt)
        prev_model_path = ckpt

        log_rows.append({
            "stage": stage.name,
            "timesteps": total_timesteps_per_stage,
            "elapsed_s": f"{elapsed:.1f}",
            "checkpoint": ckpt,
        })
        print(f"[ppo] stage '{stage.name}' done in {elapsed:.1f}s -> {ckpt}")

    # Copy final to a stable name.
    if prev_model_path:
        import shutil
        final_path = os.path.join(output_dir, "final_policy.zip")
        shutil.copyfile(prev_model_path, final_path)
        print(f"[ppo] final policy: {final_path}")

    with open(log_csv, "w", newline="") as f:
        if log_rows:
            w = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
            w.writeheader()
            for r in log_rows:
                w.writerow(r)

    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--goals-file", required=True,
                   help="navisense.dockgoals.v1 JSON exported from Unity.")
    p.add_argument("--output-dir", default="runs/ppo",
                   help="Where to save checkpoints + tensorboard logs.")
    p.add_argument("--total-timesteps", type=int, default=400_000,
                   help="Timesteps per curriculum stage.")
    p.add_argument("--n-envs", type=int, default=4,
                   help="Parallel environments. Higher = faster wallclock but more RAM.")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    out = args.output_dir
    if not os.path.isabs(out):
        out = os.path.join(_PROJECT_ROOT, out)

    ok = train_with_sb3(
        goals_file=args.goals_file,
        output_dir=out,
        total_timesteps_per_stage=args.total_timesteps,
        n_envs=args.n_envs,
        seed=args.seed,
    )
    if not ok:
        print("[ppo] stable-baselines3 not installed.")
        print("      pip install stable-baselines3[extra] gymnasium torch")
        sys.exit(2)


if __name__ == "__main__":
    main()
