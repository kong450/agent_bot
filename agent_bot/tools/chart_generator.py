"""Scientific and engineering charting utility using Matplotlib."""
from pathlib import Path
from typing import List, Optional
import datetime

class ChartGenerator:
    """Hisoblashlar va tahlillar uchun professional grafik va diagrammalar chizuvchi modul."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_line_chart(
        self,
        title: str,
        x_label: str,
        y_label: str,
        x_data: List[float],
        y_data: List[float],
        series_name: str = "Ko'rsatkich",
        filename: Optional[str] = None
    ) -> Path:
        """Chiziqli grafik (quvvat, tezlik, tushish egri chizig'i) generatsiya qiladi."""
        import matplotlib
        matplotlib.use("Agg") # No GUI mode for Telegram bot
        import matplotlib.pyplot as plt

        plt.figure(figsize=(9, 5), dpi=150)
        plt.plot(x_data, y_data, marker="o", color="#1F497D", linewidth=2.5, label=series_name)
        plt.title(f"⚡ {title}", fontsize=14, fontweight="bold", pad=12)
        plt.xlabel(x_label, fontsize=11)
        plt.ylabel(y_label, fontsize=11)
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.legend(frameon=True)
        plt.tight_layout()

        if not filename:
            filename = f"Grafik_{int(datetime.datetime.now().timestamp())}.png"

        file_path = self.output_dir / filename
        plt.savefig(str(file_path))
        plt.close()
        return file_path

    def generate_pie_chart(
        self,
        title: str,
        labels: List[str],
        values: List[float],
        filename: Optional[str] = None
    ) -> Path:
        """Xarajatlar smetasi va taqsimotlar uchun doiraviy diagramma."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        colors = ["#1F497D", "#2E75B6", "#5B9BD5", "#ED7D31", "#A5A5A5"]
        plt.figure(figsize=(7, 6), dpi=150)
        plt.pie(values, labels=labels, autopct="%1.1f%%", startangle=140, colors=colors[:len(values)])
        plt.title(f"📊 {title}", fontsize=13, fontweight="bold", pad=12)
        plt.tight_layout()

        if not filename:
            filename = f"Diagramma_{int(datetime.datetime.now().timestamp())}.png"

        file_path = self.output_dir / filename
        plt.savefig(str(file_path))
        plt.close()
        return file_path
