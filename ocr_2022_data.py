#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import pytesseract
from PIL import Image
import cv2
import numpy as np
import re
import os

def download_image(url, filename):
    """下载图片"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"下载成功: {filename}")
        return True
    except Exception as e:
        print(f"下载失败 {url}: {e}")
        return False

def preprocess_image(image_path):
    """预处理图片以提高OCR识别率"""
    # 读取图片
    img = cv2.imread(image_path)

    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 放大图片以提高识别率
    scale_factor = 2
    height, width = gray.shape
    resized = cv2.resize(gray, (width * scale_factor, height * scale_factor), interpolation=cv2.INTER_CUBIC)

    # 增加对比度
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced = clahe.apply(resized)

    # 去噪
    denoised = cv2.medianBlur(enhanced, 3)

    # 锐化
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)

    # 二值化 - 尝试多种阈值
    _, binary1 = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, binary2 = cv2.threshold(sharpened, 127, 255, cv2.THRESH_BINARY)

    # 保存多个预处理版本
    processed_path1 = image_path.replace('.jpg', '_processed1.jpg')
    processed_path2 = image_path.replace('.jpg', '_processed2.jpg')
    cv2.imwrite(processed_path1, binary1)
    cv2.imwrite(processed_path2, binary2)

    return processed_path1

def extract_text_from_image(image_path):
    """从图片中提取文字"""
    try:
        # 预处理图片
        processed_path = preprocess_image(image_path)

        # 尝试多种OCR配置
        configs = [
            r'--oem 3 --psm 6',  # 表格模式
            r'--oem 3 --psm 4',  # 单列文本
            r'--oem 3 --psm 8',  # 单词模式
            r'--oem 3 --psm 13', # 原始行模式
        ]

        best_text = ""
        max_digits = 0

        for config in configs:
            try:
                # 尝试不同的语言组合
                for lang in ['eng', 'chi_sim', 'chi_sim+eng']:
                    text = pytesseract.image_to_string(
                        Image.open(processed_path),
                        lang=lang,
                        config=config
                    )

                    # 计算识别出的数字数量，选择最好的结果
                    digit_count = len(re.findall(r'\d', text))
                    if digit_count > max_digits:
                        max_digits = digit_count
                        best_text = text

            except Exception as e:
                continue

        print(f"从 {image_path} 识别的文字:")
        print(best_text)
        print("-" * 50)

        return best_text
    except Exception as e:
        print(f"OCR识别失败 {image_path}: {e}")
        return ""

def parse_score_data(text):
    """解析识别出的文字，提取分数段数据"""
    lines = text.strip().split('\n')
    data = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 尝试匹配分数段格式：分数 人数 累计人数
        # 可能的格式：690 15 123 或 690-695 25 148
        pattern = r'(\d{3}(?:-\d{3})?)\s+(\d+)\s+(\d+)'
        match = re.search(pattern, line)
        
        if match:
            score = match.group(1)
            count = int(match.group(2))
            cumulative = int(match.group(3))
            data.append([score, count, cumulative])
            print(f"解析数据: {score} - {count} - {cumulative}")
    
    return data

def main():
    """主函数"""
    # 2022年湖北物理类一分一段表图片URL
    image_urls = [
        "https://t1.chei.com.cn/news/img/2197994161.jpg",
        "https://t1.chei.com.cn/news/img/2197994162.jpg", 
        "https://t3.chei.com.cn/news/img/2197994163.jpg",
        "https://t2.chei.com.cn/news/img/2197994164.jpg"
    ]
    
    all_data = []
    
    # 创建图片目录
    os.makedirs("images_2022", exist_ok=True)
    
    for i, url in enumerate(image_urls, 1):
        filename = f"images_2022/hubei_2022_physics_{i}.jpg"
        
        # 下载图片
        if download_image(url, filename):
            # OCR识别
            text = extract_text_from_image(filename)
            
            # 解析数据
            data = parse_score_data(text)
            all_data.extend(data)
    
    # 输出所有解析的数据
    print("\n" + "="*60)
    print("所有解析的数据:")
    print("="*60)
    
    if all_data:
        for item in all_data:
            print(f"分数: {item[0]}, 人数: {item[1]}, 累计: {item[2]}")
    else:
        print("未能成功解析出数据，可能需要手动调整OCR参数或图片预处理方法")
    
    return all_data

if __name__ == "__main__":
    extracted_data = main()
