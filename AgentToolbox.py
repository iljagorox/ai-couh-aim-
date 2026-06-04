import numpy as np
import pyautogui
import psutil
import time


class AIAgentToolbox:
    def analyze_aim_precision(self, target_box, screen_width, screen_height):
        target_center_x = (target_box[0] + target_box[2]) / 2
        target_center_y = (target_box[1] + target_box[3]) / 2
        mouse_x, mouse_y = pyautogui.position()
        distance = np.sqrt((target_center_x - mouse_x)**2 + (target_center_y - mouse_y)**2)
        score = max(0, 100 - (distance / 5))
        return {
            "distance": round(distance, 2),
            "accuracy_score": round(score, 2),
            "target_pos": (target_center_x, target_center_y)
        }

    def get_performance_metrics(self):
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        gpu_info = self._get_gpu_usage()
        return {
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "gpu_percent": gpu_info.get("gpu_percent", None),
            "gpu_memory_gb": gpu_info.get("gpu_memory_gb", None),
            "timestamp": time.time(),
        }

    def _get_gpu_usage(self):
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                return {
                    "gpu_percent": gpu.load * 100,
                    "gpu_memory_gb": round(gpu.memoryUsed / 1024, 2),
                }
        except Exception:
            pass
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            pynvml.nvmlShutdown()
            return {
                "gpu_percent": util.gpu,
                "gpu_memory_gb": round(mem_info.used / (1024**3), 2),
            }
        except Exception:
            pass
        return {}
