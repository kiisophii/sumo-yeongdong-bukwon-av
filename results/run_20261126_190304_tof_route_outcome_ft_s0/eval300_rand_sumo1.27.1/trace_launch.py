import os, sys, runpy, importlib.util
root = os.path.expanduser("~/team14_apbc")
sd = sys.argv[1]; out = sys.argv[2]
spec = importlib.util.spec_from_file_location("runner", os.path.join(root, "experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.configure(False, 0.0)
sys.path.insert(0, root); os.chdir(root)
from train import REWARD
REWARD.update(collision_penalty=10.0, arrival_bonus=10.0, blocked_penalty=0.0)
seedfile = f"{out}.seed"; open(seedfile, "w").write(sd + "\n")
os.environ["TEAM14_SEED_FILE"] = seedfile
sys.argv = ["trace_collisions.py", "--model", os.path.join(root, "results/run_20261126_190304_tof_route_outcome_ft_s0/checkpoints/model_40000.pt"), "--out", out]
runpy.run_path(os.path.join(root, "tools/trace_collisions.py"), run_name="__main__")
