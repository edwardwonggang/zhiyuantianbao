#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import os
from paddleocr import PaddleOCR
import cv2
import numpy as np

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

def preprocess_image_for_table(image_path):
    """专门针对表格的图片预处理"""
    # 读取图片
    img = cv2.imread(image_path)
    
    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 放大图片以提高识别率
    scale_factor = 3
    height, width = gray.shape
    resized = cv2.resize(gray, (width * scale_factor, height * scale_factor), interpolation=cv2.INTER_CUBIC)
    
    # 增强对比度
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced = clahe.apply(resized)
    
    # 去噪
    denoised = cv2.medianBlur(enhanced, 5)
    
    # 锐化
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)
    
    # 自适应二值化
    binary = cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    # 形态学操作去除噪点
    kernel = np.ones((2,2), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    # 保存预处理后的图片
    processed_path = image_path.replace('.jpg', '_paddle_processed.jpg')
    cv2.imwrite(processed_path, cleaned)
    
    return processed_path

def extract_table_data_with_paddleocr(image_path):
    """使用PaddleOCR提取表格数据"""
    try:
        # 预处理图片
        processed_path = preprocess_image_for_table(image_path)
        
        # 初始化PaddleOCR
        # 使用最简单的配置
        ocr = PaddleOCR(lang='ch')
        
        # 进行OCR识别
        result = ocr.predict(processed_path)
        
        print(f"\n从 {image_path} 识别的原始结果:")
        print("="*60)

        extracted_data = []

        if result:
            for res in result:
                # 从PaddleOCR结果中提取文字和置信度
                if hasattr(res, 'get') and 'rec_texts' in res and 'rec_scores' in res:
                    texts = res['rec_texts']
                    scores = res['rec_scores']

                    for text, score in zip(texts, scores):
                        print(f"文字: {text}, 置信度: {score:.3f}")

                        # 只保留置信度较高的结果
                        if score > 0.5:
                            extracted_data.append(text)

        print("-" * 60)
        
        return extracted_data
        
    except Exception as e:
        print(f"PaddleOCR识别失败 {image_path}: {e}")
        return []

def parse_table_data(text_list):
    """解析表格数据，提取分数段信息"""
    data = []
    
    # 将所有文字合并成一个字符串
    full_text = " ".join(text_list)
    print(f"合并后的文字: {full_text}")
    
    # 尝试多种正则表达式模式来匹配分数段数据
    patterns = [
        # 模式1: 分数 人数 累计人数 (用空格分隔)
        r'(\d{3})\s+(\d+)\s+(\d+)',
        # 模式2: 分数-分数 人数 累计人数
        r'(\d{3}-\d{3})\s+(\d+)\s+(\d+)',
        # 模式3: 更宽松的匹配
        r'(\d{3})\D+(\d+)\D+(\d+)',
        # 模式4: 匹配表格中的数字序列
        r'(\d{3})\s*[^\d]*(\d{1,4})\s*[^\d]*(\d{1,6})'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, full_text)
        for match in matches:
            try:
                score = match[0]
                count = int(match[1])
                cumulative = int(match[2])
                
                # 验证数据合理性
                if 400 <= int(score.split('-')[0]) <= 750 and count > 0 and cumulative > 0:
                    data.append([score, count, cumulative])
                    print(f"解析数据: {score} - {count} - {cumulative}")
            except (ValueError, IndexError):
                continue
    
    # 去重并按累计人数排序
    unique_data = []
    seen_scores = set()
    for item in data:
        if item[0] not in seen_scores:
            unique_data.append(item)
            seen_scores.add(item[0])
    
    # 按分数排序
    unique_data.sort(key=lambda x: int(x[0].split('-')[0]), reverse=True)
    
    return unique_data

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
    os.makedirs("images_2022_paddle", exist_ok=True)
    
    for i, url in enumerate(image_urls, 1):
        filename = f"images_2022_paddle/hubei_2022_physics_{i}.jpg"
        
        print(f"\n处理第 {i} 张图片...")
        print("="*60)
        
        # 下载图片
        if download_image(url, filename):
            # PaddleOCR识别
            text_list = extract_table_data_with_paddleocr(filename)
            
            # 解析数据
            data = parse_table_data(text_list)
            all_data.extend(data)
    
    # 输出所有解析的数据
    print("\n" + "="*80)
    print("PaddleOCR 解析的所有数据:")
    print("="*80)
    
    if all_data:
        # 去重并排序
        unique_data = []
        seen_scores = set()
        for item in all_data:
            if item[0] not in seen_scores:
                unique_data.append(item)
                seen_scores.add(item[0])
        
        unique_data.sort(key=lambda x: int(x[0].split('-')[0]), reverse=True)
        
        print(f"共识别出 {len(unique_data)} 个有效数据点:")
        for item in unique_data:
            print(f"分数: {item[0]}, 人数: {item[1]}, 累计: {item[2]}")
            
        return unique_data
    else:
        print("未能成功解析出数据")
        print("建议检查图片质量或调整OCR参数")
        return []

if __name__ == "__main__":
    extracted_data = main()
