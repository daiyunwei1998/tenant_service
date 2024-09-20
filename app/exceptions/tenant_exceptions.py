class DuplicateTenantNameException(Exception):
    """Custom exception for duplicate tenant name."""
    def __init__(self, message="Tenant with this name already exists"):
        self.message = message
        super().__init__(self.message)


class DuplicateTenantAliasException(Exception):
    """Custom exception for duplicate tenant alias."""
    def __init__(self, message="Tenant with this alias already exists"):
        self.message = message
        super().__init__(self.message)