from inference.processors.abstract import DataProcessor
from utils.reorder_columns import create_columns

class ColumnCreationProcessor(DataProcessor):
    def process(self, session_path: str):
        create_columns(session_path, self.language)