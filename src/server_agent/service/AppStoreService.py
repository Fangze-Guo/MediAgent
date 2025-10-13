"""
应用商店数据库服务层
负责与SQLite数据库交互，提供应用和评论的CRUD操作
"""

import sqlite3
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

class AppStoreService:
    """应用商店数据库服务类"""
    
    def __init__(self, db_path: str = "src/server_new/data/db/app.sqlite3"):
        """
        初始化服务
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        
    async def _execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        执行查询语句 (SELECT)
        Args:
            query: SQL查询语句
            params: 查询参数
        Returns:
            查询结果列表
        """
        def sync_query():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # 返回字典格式的结果
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()
        
        return await asyncio.to_thread(sync_query)
    
    async def _execute_command(self, query: str, params: tuple = ()) -> int:
        """
        执行命令语句 (INSERT, UPDATE, DELETE)
        Args:
            query: SQL命令语句
            params: 命令参数
        Returns:
            影响的行数
        """
        def sync_command():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()
        
        return await asyncio.to_thread(sync_command)
    
    # ==================== 应用相关接口 ====================
    
    async def get_apps(self, category: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取应用列表
        Args:
            category: 分类筛选 (可选)
            search: 搜索关键词 (可选)
        Returns:
            应用列表
        """
        query = "SELECT * FROM apps WHERE 1=1"
        params = []
        
        # 分类筛选
        if category and category != "全部":
            query += " AND category = ?"
            params.append(category)
        
        # 搜索功能 (搜索名称、描述、标签)
        if search:
            query += " AND (name LIKE ? OR description LIKE ? OR full_description LIKE ? OR tags LIKE ?)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])
        
        # 按评分和下载量排序
        query += " ORDER BY featured DESC, rating DESC, downloads DESC"
        
        apps = await self._execute_query(query, tuple(params))
        
        # 处理标签字段 (从逗号分隔字符串转为列表)
        for app in apps:
            app['tags'] = app['tags'].split(',') if app['tags'] else []
            # 转换布尔值
            app['installed'] = bool(app['installed'])
            app['featured'] = bool(app['featured'])
        
        return apps
    
    async def get_app_detail(self, app_id: str) -> Optional[Dict[str, Any]]:
        """
        获取应用详情
        Args:
            app_id: 应用ID
        Returns:
            应用详情信息
        """
        query = "SELECT * FROM apps WHERE id = ?"
        apps = await self._execute_query(query, (app_id,))
        
        if apps:
            app = apps[0]
            # 处理标签字段
            app['tags'] = app['tags'].split(',') if app['tags'] else []
            # 转换布尔值
            app['installed'] = bool(app['installed'])
            app['featured'] = bool(app['featured'])
            return app
        
        return None
    
    async def get_categories(self) -> List[str]:
        """
        获取所有应用分类
        Returns:
            分类列表
        """
        query = "SELECT DISTINCT category FROM apps ORDER BY category"
        rows = await self._execute_query(query)
        categories = [row['category'] for row in rows]
        return ["全部"] + categories
    
    async def get_featured_apps(self, limit: int = 6) -> List[Dict[str, Any]]:
        """
        获取精选应用
        Args:
            limit: 返回数量限制
        Returns:
            精选应用列表
        """
        query = "SELECT * FROM apps WHERE featured = 1 ORDER BY rating DESC, downloads DESC LIMIT ?"
        apps = await self._execute_query(query, (limit,))
        
        # 处理标签字段
        for app in apps:
            app['tags'] = app['tags'].split(',') if app['tags'] else []
            app['installed'] = bool(app['installed'])
            app['featured'] = bool(app['featured'])
        
        return apps
    
    async def install_app(self, app_id: str, user_id: str = "default_user") -> bool:
        """
        安装应用 (更新installed状态)
        Args:
            app_id: 应用ID
            user_id: 用户ID (简化处理，使用默认用户)
        Returns:
            是否成功
        """
        # 更新应用的installed状态
        query = "UPDATE apps SET installed = 1 WHERE id = ?"
        rows_affected = await self._execute_command(query, (app_id,))
        
        # 增加下载量
        if rows_affected > 0:
            update_downloads_query = "UPDATE apps SET downloads = downloads + 1 WHERE id = ?"
            await self._execute_command(update_downloads_query, (app_id,))
        
        return rows_affected > 0
    
    async def uninstall_app(self, app_id: str, user_id: str = "default_user") -> bool:
        """
        卸载应用 (更新installed状态)
        Args:
            app_id: 应用ID
            user_id: 用户ID (简化处理，使用默认用户)
        Returns:
            是否成功
        """
        query = "UPDATE apps SET installed = 0 WHERE id = ?"
        rows_affected = await self._execute_command(query, (app_id,))
        return rows_affected > 0
    
    # ==================== 评论相关接口 ====================
    
    async def get_app_reviews(self, app_id: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        获取应用的评论数据
        Args:
            app_id: 应用ID
            user_id: 用户ID（可选，用于获取用户点赞状态）
        Returns:
            包含评论列表、总数、平均评分、评分分布的字典
        """
        # 获取评论列表
        reviews_query = "SELECT * FROM reviews WHERE app_id = ? ORDER BY created_at DESC"
        reviews = await self._execute_query(reviews_query, (app_id,))
        
        # 如果提供了用户ID，获取该用户的点赞状态
        if user_id and reviews:
            liked_review_ids = await self.get_user_liked_reviews(app_id, user_id)
            # 为每个评论添加用户点赞状态
            for review in reviews:
                review['user_liked'] = review['id'] in liked_review_ids
        
        # 计算统计数据
        total_reviews = len(reviews)
        average_rating = 0.0
        rating_distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
        
        if total_reviews > 0:
            total_rating = sum(r['rating'] for r in reviews)
            average_rating = round(total_rating / total_reviews, 1)
            
            # 统计各星级评分数量
            for review in reviews:
                rating_distribution[str(review['rating'])] += 1
        
        return {
            "reviews": reviews,
            "total": total_reviews,
            "average_rating": average_rating,
            "rating_distribution": rating_distribution
        }
    
    async def add_review(self, app_id: str, user_name: str, rating: int, comment: str) -> bool:
        """
        添加评论
        Args:
            app_id: 应用ID
            user_name: 用户名
            rating: 评分 (1-5)
            comment: 评论内容
        Returns:
            是否成功
        """
        query = """
            INSERT INTO reviews (app_id, user_name, rating, comment, helpful_count, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
        """
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rows_affected = await self._execute_command(query, (app_id, user_name, rating, comment, current_time))
        
        # 更新应用的平均评分
        if rows_affected > 0:
            await self._update_app_rating(app_id)
        
        return rows_affected > 0
    
    async def update_review(self, review_id: int, app_id: str, user_name: str, rating: int, comment: str) -> bool:
        """
        更新评论
        Args:
            review_id: 评论ID
            app_id: 应用ID
            user_name: 用户名
            rating: 评分 (1-5)
            comment: 评论内容
        Returns:
            是否成功
        """
        # 验证评论是否存在且属于该用户
        check_query = "SELECT id FROM reviews WHERE id = ? AND app_id = ? AND user_name = ?"
        check_result = await self._execute_query(check_query, (review_id, app_id, user_name))
        
        if not check_result:
            return False
        
        # 更新评论
        update_query = """
            UPDATE reviews 
            SET rating = ?, comment = ?, created_at = ?
            WHERE id = ? AND app_id = ? AND user_name = ?
        """
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rows_affected = await self._execute_command(
            update_query, 
            (rating, comment, current_time, review_id, app_id, user_name)
        )
        
        # 更新应用的平均评分
        if rows_affected > 0:
            await self._update_app_rating(app_id)
        
        return rows_affected > 0
    
    async def delete_review(self, review_id: int, app_id: str, user_name: str) -> bool:
        """
        删除评论
        Args:
            review_id: 评论ID
            app_id: 应用ID
            user_name: 用户名
        Returns:
            是否成功
        """
        # 验证评论是否存在且属于该用户
        check_query = "SELECT id FROM reviews WHERE id = ? AND app_id = ? AND user_name = ?"
        check_result = await self._execute_query(check_query, (review_id, app_id, user_name))
        
        if not check_result:
            return False
        
        # 先删除关联的点赞记录（双重保险，即使有外键约束也手动删除）
        delete_likes_query = "DELETE FROM review_likes WHERE review_id = ?"
        await self._execute_command(delete_likes_query, (review_id,))
        
        # 删除评论
        delete_query = "DELETE FROM reviews WHERE id = ? AND app_id = ? AND user_name = ?"
        rows_affected = await self._execute_command(delete_query, (review_id, app_id, user_name))
        
        # 更新应用的平均评分
        if rows_affected > 0:
            await self._update_app_rating(app_id)
        
        return rows_affected > 0
    
    async def toggle_helpful(self, review_id: int, user_id: int) -> Dict[str, Any]:
        """
        切换用户对评论的点赞状态
        Args:
            review_id: 评论ID
            user_id: 用户ID
        Returns:
            {
                "helpful_count": int,    # 总点赞数
                "user_liked": bool       # 当前用户是否已点赞
            }
        """
        # 检查用户是否已经点赞
        check_query = "SELECT id FROM review_likes WHERE review_id = ? AND user_id = ?"
        existing_like = await self._execute_query(check_query, (review_id, user_id))
        
        if existing_like:
            # 用户已点赞，取消点赞
            delete_query = "DELETE FROM review_likes WHERE review_id = ? AND user_id = ?"
            await self._execute_command(delete_query, (review_id, user_id))
            user_liked = False
        else:
            # 用户未点赞，添加点赞记录
            insert_query = "INSERT INTO review_likes (review_id, user_id) VALUES (?, ?)"
            await self._execute_command(insert_query, (review_id, user_id))
            user_liked = True
        
        # 重新计算该评论的总点赞数
        count_query = "SELECT COUNT(*) as count FROM review_likes WHERE review_id = ?"
        count_result = await self._execute_query(count_query, (review_id,))
        helpful_count = count_result[0]['count'] if count_result else 0
        
        # 同步更新reviews表的helpful_count字段
        update_query = "UPDATE reviews SET helpful_count = ? WHERE id = ?"
        await self._execute_command(update_query, (helpful_count, review_id))
        
        return {
            "helpful_count": helpful_count,
            "user_liked": user_liked
        }
    
    async def get_user_liked_reviews(self, app_id: str, user_id: int) -> List[int]:
        """
        获取用户在某个应用下点赞的所有评论ID
        Args:
            app_id: 应用ID
            user_id: 用户ID
        Returns:
            用户点赞的评论ID列表
        """
        query = """
            SELECT rl.review_id 
            FROM review_likes rl 
            JOIN reviews r ON rl.review_id = r.id 
            WHERE r.app_id = ? AND rl.user_id = ?
        """
        result = await self._execute_query(query, (app_id, user_id))
        return [row['review_id'] for row in result] if result else []
    
    async def _update_app_rating(self, app_id: str):
        """
        更新应用的平均评分
        Args:
            app_id: 应用ID
        """
        # 计算新的平均评分
        query = "SELECT AVG(rating) as avg_rating FROM reviews WHERE app_id = ?"
        result = await self._execute_query(query, (app_id,))
        
        if result and result[0]['avg_rating']:
            new_rating = round(result[0]['avg_rating'], 1)
            # 更新应用表中的评分
            update_query = "UPDATE apps SET rating = ? WHERE id = ?"
            await self._execute_command(update_query, (new_rating, app_id))
    
    # ==================== 统计相关接口 ====================
    
    async def get_app_stats(self) -> Dict[str, Any]:
        """
        获取应用商店统计信息
        Returns:
            统计信息字典
        """
        # 总应用数
        total_apps_query = "SELECT COUNT(*) as count FROM apps"
        total_apps_result = await self._execute_query(total_apps_query)
        total_apps = total_apps_result[0]['count'] if total_apps_result else 0
        
        # 总下载量
        total_downloads_query = "SELECT SUM(downloads) as total FROM apps"
        total_downloads_result = await self._execute_query(total_downloads_query)
        total_downloads = total_downloads_result[0]['total'] if total_downloads_result else 0
        
        # 总评论数
        total_reviews_query = "SELECT COUNT(*) as count FROM reviews"
        total_reviews_result = await self._execute_query(total_reviews_query)
        total_reviews = total_reviews_result[0]['count'] if total_reviews_result else 0
        
        # 分类统计
        category_stats_query = "SELECT category, COUNT(*) as count FROM apps GROUP BY category ORDER BY count DESC"
        category_stats = await self._execute_query(category_stats_query)
        
        return {
            "total_apps": total_apps,
            "total_downloads": total_downloads,
            "total_reviews": total_reviews,
            "category_stats": category_stats
        }
    
    async def update_app_features(self, app_id: str, features: str) -> bool:
        """
        更新应用的功能特点
        Args:
            app_id: 应用ID
            features: 功能特点内容 (Markdown格式)
        Returns:
            是否成功
        """
        # 检查应用是否存在
        check_query = "SELECT id FROM apps WHERE id = ?"
        check_result = await self._execute_query(check_query, (app_id,))
        
        if not check_result:
            return False
        
        # 更新功能特点
        update_query = "UPDATE apps SET features = ? WHERE id = ?"
        rows_affected = await self._execute_command(update_query, (features, app_id))
        
        return rows_affected > 0
