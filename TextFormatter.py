def reformat_to_paragraphs(input_text, max_line_length=9000):
    """
    Reformat text into paragraph form only.
    Keeps all words, does not add/remove anything.
    Joins broken lines into full paragraphs based on blank lines.
    """
    # Split into lines
    lines = input_text.splitlines()

    paragraphs = []
    current_paragraph = []

    for line in lines:
        # If line is empty, close current paragraph
        if not line.strip():
            if current_paragraph:
                paragraphs.append(" ".join(current_paragraph))
                current_paragraph = []
        else:
            # Append line to current paragraph
            current_paragraph.append(line.strip())

    # Append last paragraph if any
    if current_paragraph:
        paragraphs.append(" ".join(current_paragraph))

    # Join paragraphs with double newlines
    return "\n\n".join(paragraphs)


# Example usage:
if __name__ == "__main__":
    # Load from file (example: transcript.txt)
    with open("transcript.txt", "r", encoding="utf-8") as f:
        text = f.read()

    formatted = reformat_to_paragraphs(text)

    # Save to new file
    with open("transcript_paragraphs.txt", "w", encoding="utf-8") as f:
        f.write(formatted)

    print("Reformatted text saved as transcript_paragraphs.txt")
