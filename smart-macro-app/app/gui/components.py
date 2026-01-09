import customtkinter as ctk

class StatusLabel(ctk.CTkLabel):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
    
    def set_loading(self):
        self.configure(text="AI Processing... Please Wait", text_color="yellow")
    
    def set_success(self, path):
        # Only show the filename to keep it short
        filename = path.split("\\")[-1] if "\\" in path else path.split("/")[-1]
        self.configure(text=f"Done! Saved: {filename}", text_color="green")
    
    def set_error(self, err):
        self.configure(text=f"Error: {err}", text_color="red")