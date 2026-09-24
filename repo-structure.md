# Billing API repository structure

The Billing API follows the shared SparrowX backend structure. `src/database.py` owns PostgreSQL configuration, `src/models.py` owns persistence models, `src/schemas.py` owns API validation, and `src/routes/invoices.py` owns invoice endpoints. The application starts from `src.main:app`.
