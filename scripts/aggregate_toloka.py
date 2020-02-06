import argparse
import json
from collections import Counter
from collections import defaultdict
from sklearn.metrics import cohen_kappa_score

def clean_text(text):
    return text.replace("\t", " ").replace("\n", " ").replace('"', '')


def main(answers_file_name, original_json, honey_output_file_name, ft_output_file_name, min_votes):
    with open(answers_file_name, "r") as r:
        header = tuple(next(r).strip().split("\t"))
        records = []
        for line in r:
            fields = line.strip().split("\t")
            assert len(fields) == len(header), fields
            records.append(dict(zip(header, fields)))
    # Filter honeypots out
    records = [r for r in records if not r["GOLDEN:res"]]

    # Normalize fields
    for r in records:
        r.pop("GOLDEN:res", None)
        r.pop("HINT:text", None)
        for key, value in r.items():
            new_key = key.split(":")[-1]
            r[new_key] = r.pop(key)

    if original_json:
        with open(original_json, "r") as r:
            data = json.load(r)
            title2url = {clean_text(d["title"]): d["url"] for d in data}
            for r in records:
                r["url"] = title2url[clean_text(r["title"])]


    # Calc inter-annotator agreement
    annotator2labels = defaultdict(dict)
    unique_keys = list(set([r["url"] for r in records]))
    unique_workers = list(set([r["worker_id"] for r in records]))
    unique_res = list(set([r["res"] for r in records]))
    res2num = {res: i for i, res in enumerate(unique_res)}
    for r in records:
        annotator2labels[r["worker_id"]][r["url"]] = r["res"]
    worker2labels = {}
    for worker_id in unique_workers:
        worker_labels = []
        worker_res = annotator2labels[worker_id]
        for key in unique_keys:
            if key not in worker_res:
                worker_labels.append(-1)
                continue
            worker_labels.append(res2num[worker_res[key]])
        worker2labels[worker_id] = worker_labels
    scores = []
    for w1, labels1 in worker2labels.items():
        for w2, labels2 in worker2labels.items():
            if w1 == w2:
                continue
            fixed_labels1 = []
            fixed_labels2 = []
            for l1, l2 in zip(labels1, labels2):
                if l1 == -1 or l2 == -1:
                    continue
                fixed_labels1.append(l1)
                fixed_labels2.append(l2)
            if not fixed_labels1 or not fixed_labels2:
                print("{} vs {}: no intersection".format(w1, w2))
            else:
                score = cohen_kappa_score(fixed_labels1, fixed_labels2)
                if -1.0 <= score <= 1.0:
                    scores.append(score)
                print("{} vs {}: {}".format(w1, w2, score))
    print("Avg kappa score: {}".format(sum(scores)/len(scores)))

    results = defaultdict(list)
    for r in records:
        results[r["url"]].append(r["res"])

    data = {r["url"]: r for r in records}
    for url, res in results.items():
        res_count = Counter(res)
        if res_count.most_common(1)[0][1] < min_votes:
            data.pop(url)

    rub_cnt = Counter()
    for _, d in data.items():
        rub_cnt[d["res"]] += 1
    print(rub_cnt.most_common())

    if honey_output_file_name:
        with open(honey_output_file_name, "w") as w:
            w.write("{}\t{}\t{}\t{}\n".format("INPUT:url", "INPUT:title", "INPUT:text", "GOLDEN:res"))
            for d in data.values():
                w.write("{}\t{}\t{}\t{}\n".format(d["url"], d["title"], d["text"], d["res"]))

    if ft_output_file_name:
        with open(ft_output_file_name, "w") as w:
            for d in data.values():
                w.write("__label__{} {} {}\n".format(d["res"], d["title"], d["text"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers-file-name", type=str, required=True)
    parser.add_argument("--original-json", type=str, default=None)
    parser.add_argument("--honey-output-file-name", type=str, default=None)
    parser.add_argument("--ft-output-file-name", type=str, default=None)
    parser.add_argument("--min-votes", type=int, default=3)
    args = parser.parse_args()
    main(**vars(args))

