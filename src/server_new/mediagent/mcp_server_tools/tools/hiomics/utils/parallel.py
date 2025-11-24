from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed, TimeoutError
import time
import gc
import signal
import os

def worker(func, kwargs_list, use_multiprocessing=True, desc="", max_workers=None, parallel_type="process", timeout=None, progress_args=None):
    """
    并行执行函数的工具
    
    Args:
        func: 要执行的函数
        kwargs_list: 参数列表
        use_multiprocessing: 是否使用多进程/多线程
        desc: 描述信息
        max_workers: 最大工作进程数
        parallel_type: 并行类型 'process' 或 'thread'
        timeout: 单个任务超时时间(秒)
        progress_args: 进度参数(保留接口兼容性，但不使用)
    """
    desc = desc or func.__name__ + ("_with_multiprocessing" if use_multiprocessing else "")
    print("\n=> total tasks:", len(kwargs_list))
    pbar = tqdm(kwargs_list, desc=desc) 
    ret = []

    if use_multiprocessing:
        if parallel_type == "process":
            executor_class = ProcessPoolExecutor
        elif parallel_type == "thread":
            executor_class = ThreadPoolExecutor
        else:
            raise ValueError(f"parallel_type must be 'process' or 'thread', but got {parallel_type}")
        
        executor = None
        try:
            executor = executor_class(max_workers=max_workers)
            futures = []
            futures_dict = {}
            
            for fid, kwargs in enumerate(kwargs_list):
                _kwargs = {k: v for k, v in kwargs.items() if not (k.startswith('__') and k.endswith('__'))}
                f = executor.submit(func, **_kwargs)
                futures.append(f)
                futures_dict[f] = (fid, kwargs.get('__name__'))
                
                time.sleep(0.01)
                if fid % 1000 == 0:
                    time.sleep(0.01)

            ret_dict = {}
            for f in as_completed(futures, timeout=timeout):
                try:
                    fid, name = futures_dict[f]
                    if name:
                        pbar.set_postfix_str(f'{name} is finished')
                    pbar.update(1)
                    
                    result = f.result(timeout=timeout)
                    ret_dict[fid] = result
                    
                except TimeoutError:
                    pbar.set_postfix_str('Task timeout, skipping...')
                    fid, name = futures_dict[f]
                    ret_dict[fid] = None
                    pbar.update(1)
                except Exception as e:
                    pbar.set_postfix_str(f'Task failed: {str(e)[:50]}...')
                    fid, name = futures_dict[f]
                    ret_dict[fid] = None
                    pbar.update(1)

            for fid, kwargs in enumerate(kwargs_list):
                ret.append(ret_dict.get(fid, None))
                
        except Exception as e:
            print(f"\nExecutor error: {e}")
            raise
        finally:
            if executor:
                executor.shutdown(wait=False, cancel_futures=True)
                
    else:
        for kwargs in pbar:
            try:
                _kwargs = {k: v for k, v in kwargs.items() if not (k.startswith('__') and k.endswith('__'))}
                name = kwargs.get('__name__')
                if name:
                    pbar.set_postfix_str(f'{name} is processing')
                    
                if timeout:
                    def timeout_handler(signum, frame):
                        raise TimeoutError("Task timeout")
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(int(timeout))
                
                result = func(**_kwargs)
                ret.append(result)
                
                if timeout:
                    signal.alarm(0)
                    
            except TimeoutError:
                pbar.set_postfix_str('Task timeout, skipping...')
                ret.append(None)
            except Exception as e:
                pbar.set_postfix_str(f'Task failed: {str(e)[:50]}...')
                ret.append(None)

    gc.collect()
    return ret