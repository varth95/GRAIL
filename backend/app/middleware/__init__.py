"""Middleware package for the GRail backend."""

from app.middleware.auth_middleware import JWTAuthMiddleware

__all__ = ["JWTAuthMiddleware"]
