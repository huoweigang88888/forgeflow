# =============================================================================
# ForgeFlow AI - Seed Data Script
# =============================================================================
# Populates the development database with sample data for testing.
# Run: make db-seed
#

import asyncio

from forgeflow.db.session import AsyncSessionLocal
from forgeflow.prompts import PromptRegistry


async def seed_prompts():
    """Seed default prompt templates (idempotent)."""
    async with AsyncSessionLocal() as session:
        registry = PromptRegistry(session)
        created = await registry.seed_default_prompts()
        if created:
            print(f"🌱 Seeded {len(created)} prompt templates:")
            for p in created:
                print(f"   - {p.prompt_name} ({p.version})")
        else:
            print("ℹ️  Prompt templates already seeded — skipping")
        return created


async def seed_policies():
    """Seed default store policies (Phase 1+)."""
    # TODO: Seed default policy documents for development
    pass


async def seed_tenants():
    """Seed pilot tenant data (Phase 1+)."""
    # TODO: Create sample tenant records
    pass


async def main():
    """Seed the database with sample data."""
    print("🌱 Seeding ForgeFlow database...\n")

    await seed_prompts()
    # await seed_policies()
    # await seed_tenants()

    print("\n✅ Seed complete")


if __name__ == "__main__":
    asyncio.run(main())
