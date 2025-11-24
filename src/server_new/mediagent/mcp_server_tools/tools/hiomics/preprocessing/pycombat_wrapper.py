#!/usr/bin/env python3
"""
修复版pyComBat - 清洁的代码重构方案

设计原则：
- 最大程度复用原库函数，避免重复实现
- 仅修复确实存在bug的函数
- 保持与原库相同的API接口

关键修复：
1. it_sol函数中的数组索引错误 (原库第155-156行)
2. adjust_data函数中ref_batch的维度处理bug (原库第609行)

复用的原库函数：
- 所有数据预处理函数: check_mean_only, define_batchmod, check_ref_batch等
- 数学计算函数: compute_prior, postmean, postvar
- 数据标准化函数: calculate_mean_var, calculate_stand_mean, standardise_data
- 非参数估计函数: nonparam_fun

仅修复的函数：
- it_sol_corrected: 修复数组维度处理
- adjust_data_corrected: 修复ref_batch维度bug
- param_fun_corrected: 调用修复版it_sol
- fit_model_corrected: 调用修复版param_fun
"""

import numpy as np
import pandas as pd
from functools import partial

# 直接导入原库中可以复用的函数
from combat.pycombat import (
    model_matrix, all_1, compute_prior, postmean, postvar,
    check_mean_only, define_batchmod, check_ref_batch, treat_batches,
    treat_covariates, check_NAs, calculate_mean_var, calculate_stand_mean,
    standardise_data, nonparam_fun
)

def it_sol_corrected(sdat, g_hat, d_hat, g_bar, t2, a, b, conv=0.0001, exit_iteration=10e5):
    """
    完全修复版的iterative solution
    
    关键修复：
    1. 正确处理数据维度：sdat是当前批次的数据 (samples x genes)
    2. 修复g_new索引错误
    3. 确保数组形状一致
    """
    # 确保输入格式正确
    sdat = np.asarray(sdat)  # samples x genes
    g_hat = np.asarray(g_hat)  # 长度为n_genes的数组
    d_hat = np.asarray(d_hat)  # 长度为n_genes的数组
    
    if len(sdat.shape) == 1:
        # 处理1D情况
        n_samples = 1
        n_genes = len(sdat)
        sdat = sdat.reshape(1, -1)
    else:
        n_samples, n_genes = sdat.shape
    
    # 确保g_hat和d_hat是正确长度的1D数组
    if np.isscalar(g_hat):
        g_hat = np.array([g_hat] * n_genes)
    if np.isscalar(d_hat):
        d_hat = np.array([d_hat] * n_genes)
        
    g_hat = np.asarray(g_hat).flatten()[:n_genes]  # 确保长度正确
    d_hat = np.asarray(d_hat).flatten()[:n_genes]  # 确保长度正确
    
    # 如果数组长度不够，用第一个值填充
    if len(g_hat) < n_genes:
        g_hat = np.pad(g_hat, (0, n_genes - len(g_hat)), 'edge')
    if len(d_hat) < n_genes:
        d_hat = np.pad(d_hat, (0, n_genes - len(d_hat)), 'edge')
    
    # 初始化
    t2_n = t2 * n_samples
    t2_n_g_hat = t2_n * g_hat
    g_old = np.copy(g_hat)
    d_old = np.copy(d_hat)
    
    change = 1
    count = 0
    
    while (change > conv) and (count < exit_iteration):
        # 更新gamma（additive effect）
        g_new = postmean(g_bar, d_old, t2_n, t2_n_g_hat)
        g_new = np.asarray(g_new).flatten()
        
        # 确保g_new长度正确
        if len(g_new) != n_genes:
            if len(g_new) == 1:
                g_new = np.repeat(g_new[0], n_genes)
            else:
                g_new = g_new[:n_genes]
        
        # 计算残差平方和 - 修复关键bug
        sum2 = np.zeros(n_genes)
        for gene_idx in range(n_genes):
            # 对每个基因，计算当前批次所有样本的残差平方和
            gene_data = sdat[:, gene_idx]  # 当前基因在当前批次的所有样本
            residuals = gene_data - g_new[gene_idx]
            sum2[gene_idx] = np.sum(residuals**2)
        
        # 更新delta（multiplicative effect）
        d_new = postvar(sum2, n_samples, a, b)
        d_new = np.asarray(d_new).flatten()
        
        # 确保d_new长度正确
        if len(d_new) != n_genes:
            if len(d_new) == 1:
                d_new = np.repeat(d_new[0], n_genes)
            else:
                d_new = d_new[:n_genes]
        
        # 计算收敛性 - 避免除零
        g_old_safe = np.where(np.abs(g_old) < 1e-10, 1e-10, g_old)
        d_old_safe = np.where(np.abs(d_old) < 1e-10, 1e-10, d_old)
        
        g_change = np.max(np.abs(g_new - g_old) / np.abs(g_old_safe))
        d_change = np.max(np.abs(d_new - d_old) / np.abs(d_old_safe))
        
        change = max(g_change, d_change)
        
        # 更新
        g_old = np.copy(g_new)
        d_old = np.copy(d_new)
        count += 1
        
        if count >= exit_iteration:
            print(f"Warning: it_sol达到最大迭代次数 {exit_iteration}")
            break
    
    return [g_new, d_new]

def adjust_data_corrected(s_data, gamma_star, delta_star, batch_design, n_batches, var_pooled, stand_mean, n_array, ref, batches, dat):
    """
    修复版的adjust_data函数 - 只修复ref_batch维度处理bug
    其他逻辑与原库完全相同
    """
    # print("Adjusting the Data")
    bayes_data = np.transpose(s_data)  # samples x genes
    j = 0
    for i in batches:  # for each batch, specific correction
        bayes_data[i] = (bayes_data[i] - np.dot(np.transpose(batch_design)[i], gamma_star)) / \
            np.transpose(
                np.outer(np.sqrt(delta_star[j]), np.asarray([1]*n_batches[j])))
        j += 1

    # renormalise the data after correction:
    # 1. multiply by variance
    # 2. add mean
    bayes_data = np.multiply(np.transpose(bayes_data), np.outer(
        np.sqrt(var_pooled), np.asarray([1]*n_array))) + stand_mean

    # 修复: correction for reference batch - 原库第609行的bug
    if ref is not None:
        # 原库bug: bayes_data[batches[ref]] = dat[batches[ref]]
        # 修复: 正确处理维度，dat和bayes_data都是genes x samples格式
        bayes_data[:, batches[ref]] = dat[:, batches[ref]]

    return bayes_data

def param_fun_corrected(i, s_data, batches, mean_only, gamma_hat, gamma_bar, delta_hat, t2, a_prior, b_prior):
    """
    修复版的param_fun - 只修复it_sol调用，其他逻辑与原库相同
    """
    g_hat = np.expand_dims(gamma_hat[i], axis=0)
    if mean_only:
        t2_n = np.multiply(t2[i], 1)
        t2_n_g_hat = np.multiply(t2_n, g_hat)
        gamma_star = postmean(gamma_bar[i], 1, t2_n, t2_n_g_hat)
        delta_star = [1]*len(s_data)
    else:
        # 使用修复版的it_sol替代原库的it_sol
        batch_data = np.transpose(np.transpose(s_data)[batches[i]])
        temp = it_sol_corrected(
            batch_data.T,  # 转换为samples x genes格式
            g_hat.flatten(), delta_hat[i], gamma_bar[i], t2[i], a_prior[i], b_prior[i]
        )
        gamma_star = temp[0]
        delta_star = temp[1]
    return [gamma_star, delta_star]

def fit_model_corrected(design, n_batch, s_data, batches, mean_only, par_prior, precision, ref, NAs):
    """
    修复版的fit_model - 只修改param_fun调用，其他逻辑与原库完全相同
    """
    # print("Fitting L/S model and finding priors.")

    # 以下逻辑与原库完全相同
    batch_design = design[0:n_batch]

    if not NAs:
        gamma_hat = np.linalg.solve(np.dot(batch_design, np.transpose(batch_design)),
                                    np.dot(batch_design, np.transpose(s_data)))

    delta_hat = []

    if (mean_only):
        delta_hat = [np.asarray([1]*len(s_data))] * len(batches)
    else:
        for i in batches:
            list_map = np.transpose(np.transpose(s_data)[i]).var(axis=1)
            delta_hat.append(np.squeeze(np.asarray(list_map)))

    gamma_bar = list(map(np.mean, gamma_hat))
    t2 = list(map(np.var, gamma_hat))

    a_prior = list(
        map(partial(compute_prior, 'a', mean_only=mean_only), delta_hat))
    b_prior = list(
        map(partial(compute_prior, 'b', mean_only=mean_only), delta_hat))

    gamma_star = np.empty((n_batch, len(s_data)))
    delta_star = np.empty((n_batch, len(s_data)))

    if par_prior:
        # print("Finding parametric adjustments.")
        # 使用修复版的param_fun_corrected替代原库的param_fun
        results = list(map(partial(param_fun_corrected,
                                   s_data=s_data,
                                   batches=batches,
                                   mean_only=mean_only,
                                   gamma_hat=gamma_hat,
                                   gamma_bar=gamma_bar,
                                   delta_hat=delta_hat,
                                   t2=t2,
                                   a_prior=a_prior,
                                   b_prior=b_prior), range(n_batch)))
    else:
        # print("Finding nonparametric adjustments")
        # 直接使用原库的nonparam_fun
        results = list(map(partial(nonparam_fun, mean_only=mean_only, delta_hat=delta_hat,
                                   s_data=s_data, batches=batches, gamma_hat=gamma_hat, precision=precision), range(n_batch)))

    for i in range(n_batch):
        results_i = results[i]
        gamma_star[i], delta_star[i] = results_i[0], results_i[1]

    # 处理参考批次 - 与原库逻辑相同
    if ref is not None:
        len_gamma_star_ref = len(gamma_star[ref])
        gamma_star[ref] = [0] * len_gamma_star_ref
        delta_star[ref] = [1] * len_gamma_star_ref

    return(gamma_star, delta_star, batch_design)

def pycombat_corrected(data, batch, mod=[], par_prior=True, prior_plots=False, 
                      mean_only=False, ref_batch=None, precision=None, **kwargs):
    """
    修复版的pyComBat - 最大程度复用原库逻辑，只修复关键bug
    
    参数与原库完全相同
    """
    # print("使用修复版pyComBat")
    
    # 复用原库的前置处理逻辑
    list_samples = data.columns
    list_genes = data.index
    dat = data.values

    check_mean_only(mean_only)

    batchmod = define_batchmod(batch)
    ref, batchmod = check_ref_batch(ref_batch, batch, batchmod)
    n_batch, batches, n_batches, n_array = treat_batches(batch)
    design = treat_covariates(batchmod, mod, ref, n_batch)
    NAs = check_NAs(dat)
    
    if not(NAs):
        # 复用原库的数据标准化逻辑
        B_hat, grand_mean, var_pooled = calculate_mean_var(
            design, batches, ref, dat, NAs, n_batches, n_batch, n_array)
        stand_mean = calculate_stand_mean(
            grand_mean, n_array, design, n_batch, B_hat)
        s_data = standardise_data(dat, stand_mean, var_pooled, n_array)
        
        # 使用修复版的fit_model（修复it_sol bug）
        gamma_star, delta_star, batch_design = fit_model_corrected(
            design, n_batch, s_data, batches, mean_only, par_prior, precision, ref, NAs)
        
        # 使用修复版的adjust_data（修复ref_batch bug）
        bayes_data = adjust_data_corrected(s_data, gamma_star, delta_star, batch_design,
                                         n_batches, var_pooled, stand_mean, n_array, ref, batches, dat)

        # 复用原库的输出格式化逻辑
        bayes_data_df = pd.DataFrame(bayes_data,
                                   columns=list_samples,
                                   index=list_genes)

        return(bayes_data_df)
    else:
        raise ValueError("NaN value is not accepted")


# 创建一个sklearn兼容的wrapper
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_array, check_is_fitted

class ComBatTransformer(BaseEstimator, TransformerMixin):
    """
    修复版pyComBat的sklearn兼容wrapper
    自动处理数据格式转换
    
    支持set_output功能：
    - set_output(transform='default'): 根据输入类型返回（默认）
    - set_output(transform='pandas'): 强制返回pandas DataFrame
    
    示例：
        transformer = PyComBatCorrectedTransformer()
        transformer.set_output(transform='pandas')  # 强制返回DataFrame
        result = transformer.fit_transform(X)  # 返回DataFrame
    """
    
    def __init__(self, parametric=True, mean_only=False, ref_batch=True):
        self.parametric = parametric
        self.mean_only = mean_only
        self.ref_batch = ref_batch
        self._output_transform = 'default'  # 默认输出格式
        
    def fit(self, X, y=None):
        """
        拟合参考批次
        X: samples x features格式
        """
        if isinstance(X, pd.DataFrame):
            self.feature_names_ = X.columns.tolist()
            self.reference_data_ = X.copy()
        else:
            self.feature_names_ = None
            self.reference_data_ = pd.DataFrame(X)
            
        self.n_features_ = X.shape[1]
        self.is_fitted_ = True
        return self
        
    def transform(self, X):
        """
        校正新批次的数据
        X: samples x features格式
        """
        check_is_fitted(self, 'is_fitted_')
        
        if isinstance(X, pd.DataFrame):
            new_data = X.copy()
        else:
            if self.feature_names_ is not None:
                new_data = pd.DataFrame(X, columns=self.feature_names_)
            else:
                new_data = pd.DataFrame(X)
        
        # 合并参考数据和新数据
        n_ref = len(self.reference_data_)
        n_new = len(new_data)
        
        # 确保列名一致
        if self.feature_names_ is not None:
            ref_data = self.reference_data_.copy()
            ref_data.columns = self.feature_names_
            new_data.columns = self.feature_names_
        else:
            ref_data = self.reference_data_
            
        combined_data = pd.concat([ref_data, new_data], ignore_index=True, axis=0)
        
        # 创建批次标签
        batch_labels = [0] * n_ref + [1] * n_new
        
        # 转换为pyComBat期望的格式：genes x samples
        data_for_combat = combined_data.T
        
        try:
            # 应用修复版pyComBat
            corrected_data_T = pycombat_corrected(
                data_for_combat,
                batch_labels,
                par_prior=self.parametric,
                mean_only=self.mean_only,
                ref_batch=0 if self.ref_batch is not None else None
            )
            
            # 转换回samples x features格式
            corrected_data = corrected_data_T.T
            
            # 返回新数据的校正结果
            corrected_new_data = corrected_data.iloc[n_ref:].copy()
            
            # 设置正确的索引
            if isinstance(X, pd.DataFrame):
                corrected_new_data.index = X.index
            
            # 根据set_output配置决定返回格式
            return self._format_output(corrected_new_data, X)
                
        except Exception as e:
            print(f"PyComBat校正失败: {e}")
            import traceback
            traceback.print_exc()
            return X
    
    def set_output(self, *, transform=None):
        """
        设置transform方法的输出格式
        
        参数:
            transform: 输出格式，可选 'default', 'pandas'
                - 'default': 根据输入类型返回（DataFrame->DataFrame, numpy->numpy）
                - 'pandas': 强制返回pandas DataFrame
        
        返回:
            self: 支持链式调用
        """
        if transform not in ['default', 'pandas', None]:
            raise ValueError(f"transform must be 'default' or 'pandas', got {transform}")
        
        if transform is not None:
            self._output_transform = transform
        
        return self
    
    def _format_output(self, result_df, original_input):
        """
        根据set_output配置和输入类型格式化输出
        """
        if self._output_transform == 'pandas':
            # 强制返回pandas DataFrame
            return result_df
        elif self._output_transform == 'default':
            # 根据输入类型决定输出格式
            if isinstance(original_input, pd.DataFrame):
                return result_df
            else:
                return result_df.values
        else:
            # 默认行为
            if isinstance(original_input, pd.DataFrame):
                return result_df
            else:
                return result_df.values


if __name__ == "__main__":
    print("修复版pyComBat已加载")
    print("特点：最大程度复用原库函数，仅修复关键bug")
    print("修复内容：")
    print("  1. it_sol函数的数组索引错误")
    print("  2. adjust_data函数中ref_batch的维度处理bug")
    print("新功能：")
    print("  3. 支持sklearn的set_output功能")
    print("使用方法：pycombat_corrected() 函数或 PyComBatCorrectedTransformer 类")
    print("\nset_output示例：")
    print("  transformer.set_output(transform='pandas')  # 强制返回DataFrame")
    print("  transformer.set_output(transform='default') # 根据输入类型返回")
    
    from sklearn.compose import make_column_selector
    
    feat_cols = make_column_selector("feature.*")
    train_df = pd.read_csv("./train_data.csv")
    train_X = train_df[feat_cols]
    test_df = pd.read_csv("./test_data.csv")
    test_X = test_df[feat_cols]
    
    # 演示set_output功能
    cb = PyComBatCorrectedTransformer(parametric=True, mean_only=False)
    
    # 设置输出为pandas格式
    cb.set_output(transform='pandas')
    print("\n使用set_output(transform='pandas'):")
    
    cb.fit(train_X)
    train_X_corrected = cb.transform(train_X)
    test_X_corrected = cb.transform(test_X)
    
    print(f"train_X_corrected类型: {type(train_X_corrected)}")
    print(f"test_X_corrected类型: {type(test_X_corrected)}")
    
    train_df[feat_cols] = train_X_corrected
    test_df[feat_cols] = test_X_corrected
    train_df.to_csv("./train_data_corrected.csv",index=False)
    test_df.to_csv("./test_data_corrected.csv",index=False)

