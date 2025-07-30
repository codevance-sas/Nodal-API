# Database Migrations in Nodal API

This document describes the database migration system used in the Nodal API project.

## Migration System Overview

The Nodal API uses [Alembic](https://alembic.sqlalchemy.org/) for database migrations. Alembic is the standard migration tool for SQLAlchemy (which SQLModel is built on) and provides a robust way to manage database schema changes.

Key features of our migration system:

1. **Version Control**: Migrations are tracked in a database table (`alembic_version`)
2. **Automatic Migration Generation**: New migrations can be generated automatically by comparing model definitions to the current database schema
3. **Bidirectional Migrations**: Support for both upgrading and downgrading the database
4. **Data Migrations**: Support for data migrations, not just schema changes
5. **Fine-grained Control**: Fine-grained control over how migrations are applied

## Using the Migration System

### Command-Line Interface

The project includes a command-line interface for working with migrations in `app/db/cli.py`. You can use this CLI to generate and apply migrations.

#### Generate a New Migration

To generate a new migration script:

```bash
python -m app.db.cli generate "Add user table"
```

This will create a new migration script in the `migrations/versions` directory. The script will include automatically generated upgrade and downgrade operations based on the differences between your models and the current database schema.

#### Apply Migrations

To apply all pending migrations:

```bash
python -m app.db.cli upgrade
```

To apply migrations up to a specific revision:

```bash
python -m app.db.cli upgrade abc123
```

#### Downgrade Migrations

To downgrade to a previous revision:

```bash
python -m app.db.cli downgrade abc123
```

#### View Migration History

To view the migration history:

```bash
python -m app.db.cli history
```

#### Check Current Revision

To check the current database revision:

```bash
python -m app.db.cli current
```

### API Endpoint

The API provides an endpoint to apply pending migrations:

```
POST /api/core/apply-migrations
```

This endpoint requires admin privileges. It applies any pending migrations and returns information about the applied migrations.

Example response:

```json
{
  "message": "Applied pending migrations",
  "previous_revision": "abc123",
  "current_revision": "def456",
  "applied_migrations": [
    "def456 (head) - Add user table"
  ]
}
```

## Creating and Applying Migrations

### Workflow for Schema Changes

1. **Modify Models**: Update your SQLModel models in the `app/models` directory
2. **Generate Migration**: Run `python -m app.db.cli generate "Description of changes"`
3. **Review Migration**: Check the generated migration script in `migrations/versions`
4. **Apply Migration**: Run `python -m app.db.cli upgrade`

### Initial Migration

To generate the initial migration script that represents the current state of the database schema:

```bash
python -m app.db.generate_initial_migration
```

This will create a migration script that includes all your current models.

### Manual Migrations

For more complex migrations, you may need to manually edit the generated migration scripts. The scripts are Python files with `upgrade()` and `downgrade()` functions that use Alembic's operations API.

Example of a manual migration:

```python
"""Add email_verified column to user table

Revision ID: abc123def456
Revises: 98765fedcba
Create Date: 2025-07-30 15:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic
revision: str = 'abc123def456'
down_revision: Union[str, None] = '98765fedcba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add a new column
    op.add_column('user', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'))
    
    # Update existing data
    op.execute("UPDATE user SET email_verified = true WHERE role = 'admin'")

def downgrade() -> None:
    # Remove the column
    op.drop_column('user', 'email_verified')
```

## Best Practices

1. **Always Review Generated Migrations**: Alembic's autogenerate feature is powerful but not perfect. Always review generated migrations before applying them.
2. **Include Data Migrations**: When changing schema in a way that affects existing data, include data migrations in the same script.
3. **Test Migrations**: Test both upgrade and downgrade operations in a development environment before applying to production.
4. **Keep Migrations Small**: Smaller, focused migrations are easier to review and less likely to cause problems.
5. **Use Meaningful Descriptions**: Use clear, descriptive messages when generating migrations to make the history easier to understand.

## Troubleshooting

### Common Issues

1. **Migration Not Detected**: If Alembic doesn't detect your model changes, make sure the model is imported in `app/models/__init__.py`.
2. **Migration Conflicts**: If you have conflicts between migrations, you may need to merge them manually or regenerate the migration.
3. **Failed Migrations**: If a migration fails, fix the issue and try again. You may need to manually fix the database state.
4. **Special Characters in Database URI**: If your database URI contains special characters like `%`, they need to be properly escaped to prevent ConfigParser interpolation errors. In the `migrations/env.py` file, make sure to escape percent signs by replacing `%` with `%%` before setting the URI in the Alembic config.

### Getting Help

For more information about Alembic, see the [official documentation](https://alembic.sqlalchemy.org/).