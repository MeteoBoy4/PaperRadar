"""打包在应用内的 Alembic 环境。"""

from alembic import context

from paper_radar.storage.schema import metadata

config = context.config


def run_migrations_online() -> None:
    connection = config.attributes["connection"]
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
