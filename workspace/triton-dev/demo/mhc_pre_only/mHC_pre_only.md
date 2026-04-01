# HC_PRE_only_forward 算子实现

## INPUT：
$x \in \mathbb{R}^{[B,S,N,D]}$,BF16
<!-- $gamma \in \mathbb{R}^{[ND]}$,FP32 (optional input) -->
$hc\_weight \in \mathbb{R}^{[ND,N]}$,FP32
$alpha\_pre \in \mathbb{R}^{[1]}$,FP32
$bias\_pre \in \mathbb{R}^{[N]}$,FP32
$hc\_mult \in \mathbb{Z}$,int32,default=4
$norm\_eps \in \mathbb{R}$,FP32,default=1e-6
$hc\_eps \in \mathbb{R}$,FP32,default=1e-6

## VEC1:所有计算在 FP32 进行
* $x\_rs \larr \text{Cast}(x).\text{Reshape}(B,S,ND), x\_rs\in\mathbb{R}^{[B,S,ND]}$, BF16 -> FP32
<!-- * if gamma is not None:
    - $x\_rs \larr x\_rs * gamma,\gamma\in\mathbb{R}^{[ND]}$ -->


## MM1:所有计算在 FP32 进行
* $H \larr x\_rs @ hc\_weight,H\in\mathbb{R}^{[B,S,N]}$

## VEC2:所有计算在 FP32 进行
* $inv\_rms \larr \text{torch.rsqrt}(x\_rs.\text{Square()}.\text{Mean(-1,keepdim=True)}+norm\_eps)$ 
    - $inv\_rms\in\mathbb{R}^{[B,S,1]}$
* $H\_tmp = H * inv\_rms,H\_tmp\in\mathbb{R}^{[B,S,N]}$
* $H\_pre \larr alpha\_pre * H\_tmp + bias\_pre,H\_pre\in\mathbb{R}^{[B,S,N]}$
* $H\_pre \larr \text{Sigmoid}(H\_pre) + hc\_eps,H\_pre\in\mathbb{R}^{[B,S,N]}$

* $h\_in\_fp \larr \text{Reduce}(H\_pre\odot x\_rs,\text{dim}=-2),h\_in\_fp\in\mathbb{R}^{[B,S,D]}$
* $h\_in \larr \text{Cast}(h\_in\_fp),h\_in\in\mathbb{R}^{[B,S,D]}$,BF16

## OUTPUT:
$h\_in \in \mathbb{R}^{[B,S,D]}$,BF16

## OPTIONAL OUTPUT （save for backward）:
$H\_mix \in \mathbb{R}^{[B,S,2N+N*N]}$,FP32
$x \in \mathbb{R}^{[B,S,N,D]}$,BF16
$inv\_rms \in \mathbb{R}^{[B,S,1]}$,FP32
$H\_pre \in \mathbb{R}^{[B,S,N]}$,FP32

