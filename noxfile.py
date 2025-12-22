import nox

nox.options.default_venv_backend = "uv"


@nox.session(python=["3.13", "3.14"])
def tests(session: nox.Session) -> None:
    session.run(
        "uv",
        "sync",
        "--dev",
        "--no-default-groups",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run("pytest", "-q")


@nox.session
def lint(session: nox.Session) -> None:
    session.run(
        "uv",
        "run",
        "ruff",
        "check",
        ".",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run(
        "uv",
        "run",
        "ruff",
        "format",
        ".",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )


@nox.session
def typecheck(session: nox.Session) -> None:
    session.run(
        "uv",
        "sync",
        "--dev",
        "--no-default-groups",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run("ty", "check", "src")
