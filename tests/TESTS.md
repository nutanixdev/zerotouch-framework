## How to Run Tests with Coverage

To run the tests and generate a coverage report for the `tests/unit/` directory, use the following command:

```bash
pytest --cov=framework --cov-report=html --cov-config=.coveragerc

This will generate the coverage report in the htmlcov directory.
You can open the index.html file inside the htmlcov folder to view the coverage report in your browser.