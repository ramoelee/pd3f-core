from cleantext import clean
from joblib import Memory

from .score import score_perplexity

memory = Memory("~/.ddd-cache", verbose=0)

# dehyphenation
@memory.cache
def dehyphen(lines):
    # special format. 2D List, word should not contain whitespace, except the last words per line
    later_options = []
    later_idx = []

    for idx, l in enumerate(lines):
        # don't work on last line
        if idx == len(lines) - 1:
            continue
        last_word = l[-1]

        # don't work if ther has to be a newline
        if last_word[-1] == "\n":
            continue

        last_char = clean(last_word.strip()[-1])
        if last_char != "-":
            continue

        next_word = lines[idx + 1][0]

        # 1. two words (e.g. part of an abrev.), so do nothing
        option1 = last_word + next_word

        # 2. some compound-word (keep hyphen), remove whitespace
        option2 = last_word.strip() + next_word

        # 3. remove hyphen, most likely to happen
        option3 = last_word.strip()[:-1] + next_word

        later_options += [option1, option2, option3]
        later_idx.append(idx)

    # do it all with one request
    all_scores = score_perplexity(later_options, sync=True)

    for i, idx in enumerate(later_idx):
        _, option2, option3 = later_options[i * 3 : i * 3 + 3]
        scores = all_scores[i * 3 : i * 3 + 3]
        print(scores)
        best_score_idx = scores.index(min(scores))
        assert best_score_idx in (0, 1, 2)

        # option1: don't change anything

        if best_score_idx == 1:
            lines[idx + 1][0] = " " + option2
            lines[idx].pop()

        if best_score_idx == 2:
            lines[idx + 1][0] = " " + option3
            lines[idx].pop()

    return lines


@memory.cache
def is_split_paragraph(para1, para2):
    options = []
    # the lines may have newlines or whitespace in the end
    options.append(" ".join(para1[-1]) + "\n\n" + " ".join(para2[0]))
    options.append(" ".join(para1[-1] + para2[0]))

    last_word_para1 = para1[-1][-1]
    if clean(last_word_para1[-1]) == "-":
        options.append(" ".join(para1[-1])[:-1] + " ".join(para2[0]))

    scores = score_perplexity(options, sync=True)

    print(options)
    print(scores)

    best_score_idx = scores.index(min(scores))

    if best_score_idx == 0:
        return None
    if best_score_idx == 1:
        para1[-1][-1] += " "
        return para1 + para2
    if best_score_idx == 2:
        # joins the last word of para2 with the first word of para1
        para1[-1][-1] = last_word_para1[:-1] + para2[0].pop(0) + " "
        return para1 + para2
