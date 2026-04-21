import numpy as np
import pyautogui

class AIAgentToolbox:
    # ... (предыдущий код) ...

    def analyze_aim_precision(self, target_box, screen_width, screen_height):
        """
        Анализирует точность наводки.
        target_box: [x1, y1, x2, y2] - координаты цели от модели
        """
        # 1. Находим центр цели
        target_center_x = (target_box[0] + target_box[2]) / 2
        target_center_y = (target_box[1] + target_box[3]) / 2
        
        # 2. Получаем текущую позицию курсора
        mouse_x, mouse_y = pyautogui.position()
        
        # 3. Считаем дистанцию (Евклидово расстояние)
        distance = np.sqrt((target_center_x - mouse_x)**2 + (target_center_y - mouse_y)**2)
        
        # Чем меньше дистанция, тем лучше результат
        score = max(0, 100 - (distance / 5)) 
        
        return {
            "distance": round(distance, 2),
            "accuracy_score": round(score, 2),
            "target_pos": (target_center_x, target_center_y)
        }

    def get_performance_metrics(self):
        """Возвращает данные о нагрузке для вывода в GUI"""
        # Здесь будет логика сбора данных о GPU/RAM, как ты просил
        pass