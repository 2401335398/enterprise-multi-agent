from dotenv import load_dotenv

load_dotenv()

from app.observability.langfuse_integration import (
    get_langfuse_client,
)


def main():

    langfuse = (
        get_langfuse_client()
    )

    if langfuse is None:
        print(
            "[LANGFUSE] disabled"
        )
        return

    print(
        "[LANGFUSE] auth:",
        langfuse.auth_check()
    )

    with (
        langfuse
        .start_as_current_observation(
            as_type="span",
            name=(
                "langfuse-connection-test"
            ),
        )
    ) as span:

        span.update(
            input={
                "message":
                    (
                        "hello from "
                        "enterprise-multi-agent"
                    )
            },
            output={
                "status":
                    "success"
            },
        )

    print(
        "[LANGFUSE] flushing..."
    )

    langfuse.flush()

    print(
        "[LANGFUSE] test trace flushed."
    )


if __name__ == "__main__":
    main()
