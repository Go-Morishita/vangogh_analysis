import csv
import glob
import os
import statistics

# --------- 1. 画像の平均RGBを求める関数（既存を想定）---------
# 既存のfunctions.pyにある場合はfrom functions import get_average_rgbなどでインポートしてください。
# ここでは簡易サンプルとして定義しています。


def get_average_rgb(image_path):
    from PIL import Image
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        width, height = img.size
        pixels = img.load()
        r_sum = g_sum = b_sum = 0
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                r_sum += r
                g_sum += g
                b_sum += b
        num_pixels = width * height
        return (r_sum / num_pixels, g_sum / num_pixels, b_sum / num_pixels)

# --------- 2. JSONファイル（好感度データ）を読み込む関数 ---------


def load_impression_data_from_tsv(tsv_file):
    """
    タブ区切りのアンケート結果ファイルから、
    画像（列 "1" ~ "10"）の平均好感度を計算し、
    {"image_01": 平均値, "image_02": 平均値, ...} のような辞書を返す。
    """
    sums = [0] * 10     # 各画像(1〜10)の合計値
    count = 0           # 有効行数

    with open(tsv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)  # ヘッダー行を読み飛ばす
        # 例: header = ["タイムスタンプ", "1", "2", ..., "10"]

        for row in reader:
            # row[0] -> タイムスタンプ（例: "2025/01/03 1:20:12"）
            # row[1] ~ row[10] -> 画像1〜10の回答値
            # ※データが欠損しない前提で int(row[i]) が可能
            for i in range(1, 11):
                sums[i-1] += int(row[i])
            count += 1

    # 平均値を計算
    impression_data = {}
    for i in range(10):
        if count > 0:
            avg_value = sums[i] / count
        else:
            avg_value = 0  # 行がない場合は0など
        # "image_01" ~ "image_10" というキーに平均値をセット
        impression_data[f"image_{i+1:02d}"] = avg_value

    return impression_data

# --------- 3. 画像パス一覧を取得する関数 ---------


def get_image_paths(folder, pattern="image*.jpg"):
    """
    指定フォルダ内の画像パスをソートして取得し、リストとして返す。
    """
    paths = sorted(glob.glob(os.path.join(folder, pattern)))
    return paths

# --------- 4. CSVに書き込む処理を行う関数 ---------


def write_csv_output(image_paths, impression_data, output_path, filename):
    """
    画像パス一覧と好感度データをもとに、平均RGB＋好感度をまとめたCSVを作成する。
    """
    with open(output_path / filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile, delimiter="\t")
        # ヘッダー行
        writer.writerow(["filename", "Red_ave", "Green_ave",
                        "Blue_ave", "Impression"])

        # 画像ごとに処理
        for image_path in image_paths:
            filename = os.path.basename(image_path)  # 例: "image_01.jpg"
            image_id = os.path.splitext(filename)[0]  # 例: "image_01"

            # 平均RGBを取得
            avg_r, avg_g, avg_b = get_average_rgb(image_path)

            # 好感度データを取得（なければ "N/A" ）
            impression = impression_data.get(image_id, "N/A")

            # CSVに1行追加
            writer.writerow([
                filename,
                f"{avg_r:.2f}",
                f"{avg_g:.2f}",
                f"{avg_b:.2f}",
                impression
            ])


def load_image_variances_from_tsv(tsv_file, alpha):
    """
    タブ区切りのアンケート結果ファイルから
      - 各画像 (列 1~10) の平均値 mean
      - 標準偏差 std
      - 重み weight = 1 / (1 + std) など
    を算出し、辞書で返す。
    例:
    {
      "image_01": {"mean": x, "std": y, "weight": w},
      "image_02": {...},
      ...
    }
    """
    # 画像1~10のスコアをまとめる入れ物
    all_scores = [[] for _ in range(10)]

    with open(tsv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)  # 先頭行を読み飛ばし
        # header = ["タイムスタンプ","1","2",...,"10"]

        for row in reader:
            # row[1]~row[10] -> 画像1~10の評価スコア
            for i in range(1, 11):
                val = int(row[i])
                all_scores[i-1].append(val)

    results = {}
    for i in range(10):
        scores = all_scores[i]
        if len(scores) == 0:
            mean_val = 0
            std_val = 0
        else:
            mean_val = statistics.mean(scores)
            std_val = statistics.pstdev(scores)  # 母標準偏差か標本標準偏差かは用途に応じて

        # 分散が大きいほど weight を小さくする例
        raw_weight = mean_val - alpha * std_val
        weight = raw_weight if raw_weight > 0 else 0

        # image_01 ~ image_10 のキー
        key = f"image_{i+1:02d}"
        results[key] = {
            "mean": mean_val,
            "std": std_val,
            "weight": weight
        }

    return results


def extract_weights(variances_data):
    """
    variances_data 形式:
    {
      "image_01": {"mean": x, "std": y, "weight": w1},
      "image_02": {"mean": x, "std": y, "weight": w2},
      ...
      "image_10": {"mean": x, "std": y, "weight": w10}
    }
    のような辞書を受け取り、["image_01", "image_02", ..., "image_10"] の順に 
    "weight" だけをリストで返す。

    返り値の例: [w1, w2, ..., w10]
    """
    weights = []
    for i in range(1, 11):
        key = f"image_{i:02d}"
        if key in variances_data:
            w = variances_data[key]["weight"]
            weights.append(w)
        else:
            # 万一キーがなければ、0やNoneなど適宜扱いやすい値を追加
            weights.append(None)

    return weights
