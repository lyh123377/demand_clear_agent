#!/usr/bin/env python3
"""
简易代码收集器（支持 Python、JavaScript、CSS、HTML）
"""

import os


def collect_code(input_folder, output_file="all_code.txt"):
    """收集指定类型代码文件到单个文件"""

    # 检查输入文件夹
    if not os.path.exists(input_folder):
        print(f"错误：找不到文件夹 '{input_folder}'")
        return

    # 定义支持的文件扩展名
    extensions = ('.py', '.js', '.css', '.html')

    # 查找所有匹配的文件
    code_files = []
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            if file.endswith(extensions):
                code_files.append(os.path.join(root, file))

    if not code_files:
        print("未找到任何 .py/.js/.css/.html 文件！")
        return

    print(f"找到 {len(code_files)} 个代码文件")

    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for file_path in code_files:
            # 写入文件名和路径
            out_f.write(f"\n{'#' * 60}\n")
            out_f.write(f"# 文件名: {os.path.basename(file_path)}\n")
            out_f.write(f"# 路径: {file_path}\n")
            out_f.write(f"{'#' * 60}\n\n")

            # 写入文件内容，尝试 utf-8 和 gbk 编码
            try:
                with open(file_path, 'r', encoding='utf-8') as in_f:
                    out_f.write(in_f.read())
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='gbk') as in_f:
                        out_f.write(in_f.read())
                except Exception as e:
                    out_f.write(f"# 无法读取此文件（编码错误）: {e}\n")
            except Exception as e:
                out_f.write(f"# 无法读取此文件: {e}\n")

            out_f.write("\n\n")

    print(f"完成！代码已保存到: {output_file}")


# 使用示例
if __name__ == "__main__":
    folder_to_scan = input("请输入要扫描的文件夹路径（默认当前文件夹）: ").strip()
    if not folder_to_scan:
        folder_to_scan = "."

    output_filename = input("请输入输出文件名（默认: all_code.txt）: ").strip()
    if not output_filename:
        output_filename = "all_code.txt"

    collect_code(folder_to_scan, output_filename)