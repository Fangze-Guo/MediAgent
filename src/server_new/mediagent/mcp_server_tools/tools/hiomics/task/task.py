from copy import deepcopy
from pathlib import Path
import yaml
import json
import shutil
import pickle
import time
from collections import OrderedDict
from hiomics.utils import create_object


class TrainTask:
    def __init__(self, task_name, task_dir):
        self.task_name = task_name
        self.task_dir = Path(task_dir)
        self.mode = "train"

        self.data_root = self.task_dir / "data"
        self.data_root.mkdir(parents=True, exist_ok=True)

        self.step_root = self.task_dir / "step"
        self.step_root.mkdir(parents=True, exist_ok=True)

        # ===============================================
        self._steps = OrderedDict()
        self._data = OrderedDict()

    def add_data(self, data_name, data_obj):
        info = {
            "task_name": self.task_name,
            "data_name": data_name,
            "data_class": f"{data_obj.__class__.__module__}.{data_obj.__class__.__qualname__}",
            "data_type": type(data_obj).__name__,
            "data_kwargs": data_obj.to_kwargs(),
            "timestamp": time.time(),
        }
        data_dir = self.data_root / data_name
        data_dir.mkdir(parents=True, exist_ok=True)
        with open(data_dir / f"info.json", "w") as f:
            json.dump(info, f, indent=4)
        self._data[data_name] = data_obj
        # with open(data_dir / f"data.pkl", "wb") as f:
        #     pickle.dump(data_obj, f)

    def add_step(self, step_name, step_obj, input_map):
        info = {
            "task_name": self.task_name,
            "step_name": step_name,
            "step_class": f"{step_obj.__class__.__module__}.{step_obj.__class__.__qualname__}",
            "step_type": type(step_obj).__name__,
            "step_kwargs": step_obj.to_kwargs(),
            "step_input_map": input_map,
            "timestamp": time.time(),
        }
        step_dir = self.step_root / step_name
        step_dir.mkdir(parents=True, exist_ok=True)
        with open(step_dir / f"info.json", "w") as f:
            json.dump(info, f, indent=4)
        # different from data, step_obj will be saved after run
        self._steps[step_name] = (step_obj, input_map)

    def run_step(self, step_name, **kwargs):
        assert step_name in self._steps, f"Step {step_name} not found"
        step_obj, input_map = self._steps[step_name]
        step_dir = self.step_root / f"{step_name}"
        step_dir.mkdir(parents=True, exist_ok=True)
        result_dir = self.data_root / f"{step_name}"
        result_dir.mkdir(parents=True, exist_ok=True)

        input_data = {
            k: self._data[v] for k, v in input_map.items()
        }
        
        res = step_obj.run(step_dir=step_dir, result_dir=result_dir, **input_data, **kwargs)
        self.add_data(step_name, res)

        step_obj.save(step_dir=step_dir, input_map=input_map, result_dir=result_dir)
    
    def save(self, save_pkl=False):
        if save_pkl:
            with open(self.task_dir / "task.pkl", "wb") as f:
                pickle.dump(self, f)
        
        info = {
            "task_name": self.task_name,
            "task_dir": str(self.task_dir),
            "mode": self.mode,
            "data_list": [_ for _ in self._data.keys()],
            "step_list": [_ for _ in self._steps.keys()],
            "timestamp": time.time(),
        }
        with open(self.task_dir / "info.json", "w") as f:
            json.dump(info, f, indent=4)
    
    @classmethod
    def load(cls, task_dir):
        with open(task_dir / "task.pkl", "rb") as f:
            task = pickle.load(f)
        return task
        


class TestTask(TrainTask):
    def __init__(self, task_name, task_dir):
        super().__init__(task_name, task_dir)
        self.mode = "test"

    def clone_steps(self, train_task_dir=None, train_task=None):
        if train_task is not None:
            shutil.rmtree(self.step_root)
            shutil.copytree(train_task.step_root, self.step_root)
            self._steps = deepcopy(train_task._steps)
        elif train_task_dir is not None:
            train_task_dir = Path(train_task_dir)
            assert (train_task_dir / "info.json").exists(), f"Train task info not found in {train_task_dir}"
            with open(train_task_dir / "info.json", "r") as f:
                info = json.load(f)

            shutil.rmtree(self.step_root)
            shutil.copytree(train_task_dir / "step", self.step_root)
            for step_name in info["step_list"]:
                step_dir = self.step_root / step_name
                assert (step_dir / "step.pkl").exists(), f"Step pickle not found in {step_dir}"
                with open(step_dir / "step.pkl", "rb") as f:
                    tmp = pickle.load(f)
                    step_obj = tmp["step_obj"]
                    if "input_map" in tmp:
                        input_map = tmp["input_map"]
                    else:
                        input_map = {}
                self._steps[step_name] = (step_obj, input_map)
        else:
            raise ValueError("Either train_task or train_task_dir must be provided")
    


