import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import logging, time
logging.basicConfig(filename='saga_launch.log', level=logging.DEBUG, format='%(asctime)s %(message)s')
logging.info('Starting saga launcher')

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class DummyCore:
    brain_model = "gemma4-opencode"
    ollama_host = "http://localhost:11434"
    def ollama_chat_options(self, temp=0.7):
        return {"temperature": temp}
    def _ollama_keep_alive_kw(self):
        return {}

root = ctk.CTk()
root.withdraw()
logging.info('Root created')

from neural_saga import SagaPlayWindow
logging.info('Import done')

win = SagaPlayWindow(root, DummyCore(), memory_store={}, skin="cyber", log_fn=lambda m: logging.info(f'SAGA: {m}'))
logging.info('Window created')

def check_loop():
    logging.info(f'Tick: {win._game_tick:.1f}, busy={win._busy}')
    root.after(5000, check_loop)
root.after(5000, check_loop)

root.after(180000, root.destroy)
root.mainloop()
logging.info('Done')
