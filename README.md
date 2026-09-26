## Installation Instructions

This project is a beginner-friendly starter for working with financial data. It has a Streamlit web app (`app.py`, with logic in `src/`) built from the code in the `notebooks/` folder.

## Run the Streamlit app

After installing the packages (steps below), run:

```bash
streamlit run app.py
```

Then enter a ticker (e.g. `MU`), choose an analysis type (filings, news, or stock price ratings) and click **Run**.

- `app.py`: the Streamlit UI in the project root (the file you run).
- `src/analysis.py`: the logic, with functions taken from the notebooks (`get_financials`, `get_news`, `get_price`, `get_analyst_ratings`).

## Installation Instructions

1. Open a terminal in the project folder.

   ```bash
   cd /workspaces/smu-cce-starter
   ```

2. Create a virtual environment so your packages stay organized.

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Upgrade pip and install the required packages.

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. If Jupyter is not already available, install it.

   ```bash
   python -m pip install notebook
   ```

5. Start Jupyter and open a notebook.

   ```bash
   jupyter notebook
   ```

6. Open one of the files in the notebooks folder and run the cells from top to bottom.

> You can also explore the raw code by opening the notebooks in Jupyter.

## Code Walkthrough

The main work in this repo lives in the notebooks folder. Each notebook is a small data task that uses Yahoo Finance to pull stock information.

- notebooks/stock_price_ratings.ipynb: gets a stock's current price and shows analyst recommendation data.
- notebooks/news.ipynb: fetches recent news headlines and summaries for a stock ticker.
- notebooks/filings.ipynb: pulls financial statements such as income statements, balance sheets, and cash flow.

Each notebook starts by importing the yfinance library, which connects to Yahoo Finance. The code then defines a function such as get_price(), get_news(), or get_financials(). After that, the notebook calls the function with a stock ticker such as MU or GOOG. The result is printed in the notebook so you can see the raw data in an easy-to-read format.

From start to finish, the workflow is simple:

1. Choose a stock ticker.
2. Run the notebook cell that defines the function.
3. Call the function with the ticker.
4. View the output data in the notebook.
5. Use that data to explore the stock, news, or financial statements.

This is a good starter project for learning how Python notebooks connect to live data, cleanly organize code, and prepare for building a larger financial or cloud-based application later.

 # Cloud Computing for Economics: Starter Repo 

  This repository contains the starter code and lesson materials for building a Python financial-data application and deploying it to AWS.

  Students will use GitHub Codespaces, Python, Jupyter notebooks, Streamlit, Git, and AWS CloudFormation.

  ## Learning outcomes

  By the end of the course, you will be able to:

   1.  Build and deploy an analytics application with a simple Front End / back-end (using AI)
   2.  Host and share the application on a cloud platform (e.g., AWS EC2 or similar) so that others can access it securely over the web
   3.  Integrate data sources and APIs into the app to enable interactive, real-time analytics
   4.  Apply cloud architecture best practices, ensuring the app demonstrates scalability, performance efficiency, and basic security
   5.  Showcase your work on GitHub as part of a personal portfolio, demonstrating practical cloud and analytics skills through a shareable, explorable repository

  
  ## Repository structure

  ```text
  .
  ├── lessons/          # Step-by-step course instructions
  ├── notebooks/        # Starter financial-data notebooks
  ├── app.py            # Streamlit app (run this)
  ├── src/              # Logic (analysis.py)
  ├── requirements.txt  # Python dependencies
  └── README.md         # Course overview