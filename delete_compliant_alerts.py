"""
删除合规行为告警记录脚本
删除数据库中violation_type为chef_uniform和chef_hat的记录
"""
import sys
import os

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from models.database import init_db, get_db, Alert

def delete_compliant_alerts():
    """删除合规行为告警记录"""
    print("=" * 50)
    print("删除合规行为告警记录")
    print("=" * 50)
    
    # 初始化数据库
    init_db()
    db = next(get_db())
    
    try:
        # 查找合规行为记录
        chef_uniform_count = db.query(Alert).filter(Alert.violation_type == 'chef_uniform').count()
        chef_hat_count = db.query(Alert).filter(Alert.violation_type == 'chef_hat').count()
        
        print(f"\n找到合规行为记录:")
        print(f"  - 穿工作服 (chef_uniform): {chef_uniform_count} 条")
        print(f"  - 戴厨师帽 (chef_hat): {chef_hat_count} 条")
        print(f"  - 总计: {chef_uniform_count + chef_hat_count} 条")
        
        if chef_uniform_count == 0 and chef_hat_count == 0:
            print("\n没有需要删除的记录")
            return
        
        # 确认删除
        confirm = input("\n确认删除以上记录？(y/n): ")
        if confirm.lower() != 'y':
            print("取消删除")
            return
        
        # 删除记录
        deleted_uniform = db.query(Alert).filter(Alert.violation_type == 'chef_uniform').delete()
        deleted_hat = db.query(Alert).filter(Alert.violation_type == 'chef_hat').delete()
        
        db.commit()
        
        print(f"\n成功删除 {deleted_uniform + deleted_hat} 条记录")
        print(f"  - 穿工作服: {deleted_uniform} 条")
        print(f"  - 戴厨师帽: {deleted_hat} 条")
        
        # 验证删除结果
        remaining = db.query(Alert).count()
        print(f"\n数据库剩余告警记录: {remaining} 条")
        
    except Exception as e:
        db.rollback()
        print(f"\n删除失败: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    delete_compliant_alerts()