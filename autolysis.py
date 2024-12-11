import os
import sys
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from typing import Dict, Any
import json
import httpx
import base64
from io import BytesIO
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


class AutolysisAnalyzer:
    def __init__(self, csv_path: str):
        """
        Initialize the analyzer with the CSV file path
        
        Args:
            csv_path (str): Path to the input CSV file
        """
        # Validate input file
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        # Load the dataset with multiple encoding attempts
        try:
            # Try reading with different encodings
            encodings_to_try = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            
            for encoding in encodings_to_try:
                try:
                    self.df = pd.read_csv(csv_path, encoding=encoding)
                    print(f"Successfully read CSV with {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"Could not read CSV with any of these encodings: {encodings_to_try}")
        
        except Exception as e:
            raise ValueError(f"Error reading CSV: {e}")
        
        # AI Proxy token from .env
        self.ai_token = os.getenv("AIPROXY_TOKEN")
        if not self.ai_token:
            raise ValueError("AIPROXY_TOKEN not found in .env file")
        
        # Client for API calls
        self.client = httpx.Client(
            base_url="https://aiproxy.sanand.workers.dev",
            headers={
                "Authorization": f"Bearer {self.ai_token}",
                "Content-Type": "application/json"
            },
            timeout=120.0
        )

    def generate_dataset_overview(self) -> Dict[str, Any]:
        """
        Generate a comprehensive overview of the dataset
        
        Returns:
            Dict containing dataset metadata
        """
        overview = {
            "shape": self.df.shape,
            "columns": list(self.df.columns),
            "column_types": {col: str(self.df[col].dtype) for col in self.df.columns},
            "missing_values": self.df.isnull().sum().to_dict(),
            "summary_statistics": self.df.describe().to_dict()
        }
        return overview

    def perform_generic_analysis(self):
        """
        Conduct generic data analysis
        """
        # Correlation matrix
        corr_matrix = self.df.select_dtypes(include=[np.number]).corr()
        plt.figure(figsize=(10, 8))
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', linewidths=0.5)
        plt.title('Correlation Heatmap')
        plt.tight_layout()
        plt.savefig('correlation_heatmap.png')
        plt.close()

        # Distribution of numeric columns
        numeric_columns = self.df.select_dtypes(include=[np.number]).columns
        plt.figure(figsize=(15, 5))
        for i, col in enumerate(numeric_columns[:3], 1):
            plt.subplot(1, 3, i)
            sns.histplot(self.df[col], kde=True)
            plt.title(f'Distribution of {col}')
        plt.tight_layout()
        plt.savefig('numeric_distributions.png')
        plt.close()

    def query_llm(self, messages: list) -> str:
        """
        Query the LLM with given messages
        
        Args:
            messages (list): List of message dictionaries
        
        Returns:
            str: LLM's response
        """
        try:
            # Updated endpoint and payload structure
            response = self.client.post(
                "/openai/v1/chat/completions", 
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "max_tokens": 1000
                }
            )
            
            # Print full response for debugging
            print("Full API Response:", response.text)
            
            # Raise an exception for bad responses
            response.raise_for_status()
            
            # Extract content safely
            response_json = response.json()
            if 'choices' in response_json and response_json['choices']:
                return response_json['choices'][0]['message']['content']
            else:
                raise ValueError("No valid response from LLM")
    
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error: {e}")
            print(f"Response Text: {e.response.text}")
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise


    def generate_story(self, overview: Dict[str, Any]) -> str:
        """
        Generate a narrative story about the dataset
        
        Args:
            overview (Dict): Dataset overview metadata
        
        Returns:
            str: Narrative markdown
        """
        story_prompt = [
            {"role": "system", "content": "You are a data storyteller. Write an engaging markdown narrative about a dataset."},
            {"role": "user", "content": f"""
            I have a dataset with the following characteristics:
            - Total Rows: {overview['shape'][0]}
            - Total Columns: {overview['shape'][1]}
            - Columns: {', '.join(overview['columns'])}
            - Column Types: {json.dumps(overview['column_types'], indent=2)}
            - Missing Values: {json.dumps(overview['missing_values'], indent=2)}

            Tell a compelling story about this data. Include:
            1. A brief description of the dataset
            2. Interesting observations from the summary statistics
            3. Potential insights or implications
            4. Recommendations for further analysis
            """}
        ]

        story = self.query_llm(story_prompt)
        
        # Add charts to the story
        story += "\n\n## Data Visualizations\n\n"
        story += "![Correlation Heatmap](correlation_heatmap.png)\n\n"
        story += "![Numeric Distributions](numeric_distributions.png)\n"

        return story

    def run_analysis(self):
        """
        Main analysis method
        """
        # Generate dataset overview
        overview = self.generate_dataset_overview()
        
        # Perform generic analysis and generate visualizations
        self.perform_generic_analysis()
        
        # Generate narrative story
        story = self.generate_story(overview)
        
        # Write README.md
        with open('README.md', 'w') as f:
            f.write(story)

def main():
    if len(sys.argv) != 2:
        print("Usage: uv run autolysis.py <dataset.csv>")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    analyzer = AutolysisAnalyzer(csv_path)
    analyzer.run_analysis()
    print("Analysis complete. Check README.md and generated charts.")
    

if __name__ == "__main__":
    main()