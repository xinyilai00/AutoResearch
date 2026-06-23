# Comparative Cariogenic and Erosive Potential of Halloween Candy Types: A Computational Modeling Study of Sugar Release Kinetics, Oral Retention, and Acidogenic pH Dynamics

## Abstract

Halloween represents a unique temporal event in which children experience concentrated, episodic exposure to large quantities of confectionery products over a period of days to weeks. While the relationship between chronic dietary sugar consumption and dental caries is well-established in the pediatric oral health literature, the cariogenic potential of different candy types commonly distributed during Halloween has not been systematically compared using computational modeling approaches. This study addresses a critical gap in understanding whether candy matrix properties—including dissolution kinetics, adhesiveness, and exogenous acid content—produce differential cariogenic and erosive risk profiles across four major candy categories: chocolate, gummy/sticky candies, hard candies, and sour candies. A computational simulation framework was designed to integrate publicly available nutritional composition data with established oral physiology parameters, modeling sugar release kinetics, salivary clearance dynamics, and plaque pH responses over a 60-minute post-consumption window. The simulation employed a modified Stephan curve model incorporating Michaelis-Menten bacterial fermentation kinetics and bicarbonate buffering to predict four cariogenicity metrics: time below critical pH 5.5, area under the pH deficit curve, minimum pH nadir, and cumulative acid exposure index. Statistical comparison across candy types was planned using one-way ANOVA with Tukey HSD post-hoc tests. The study hypothesized that gummy/sticky candies would exhibit the highest cariogenic potential due to prolonged oral retention and sustained sugar release, followed by sour candies (combining high sugar with exogenous acids), hard candies, and chocolate. However, experimental execution was not completed due to infrastructure limitations requiring custom computational runners beyond the available automated pipeline capabilities. This paper presents the complete methodological framework, computational model specification, and planned analytical approach, establishing a reproducible protocol for future empirical investigation of candy-type-specific cariogenic risk assessment.

**Keywords:** dental caries, Halloween candy, sugar release kinetics, Stephan curve, computational modeling, oral microbiome, pediatric oral health, cariogenic potential

## Introduction

Dental caries remains the most prevalent chronic disease among children worldwide, affecting approximately 60-90% of school-aged children in industrialized nations (Petersen, 2003; WHO, 2022). The etiology of dental caries is multifactorial, involving the complex interplay of cariogenic bacteria, fermentable carbohydrates, host susceptibility, and time (Keyes, 1962; Newbrun, 1982). Among these factors, dietary sugar consumption represents the most modifiable risk factor and has been the focus of extensive public health intervention efforts spanning decades (Moynihan & Kelly, 2014; Sheiham & James, 2015).

The relationship between sugar and dental caries operates through a well-characterized biochemical pathway. Oral bacteria, particularly *Streptococcus mutans* and lactobacilli, metabolize fermentable carbohydrates to produce organic acids—primarily lactic acid—that lower plaque pH below the critical threshold of approximately 5.5, initiating enamel demineralization (Featherstone, 2000; Zero, 2004). The frequency and duration of acid exposure, rather than merely the total quantity of sugar consumed, are recognized as critical determinants of cariogenic risk (Gustafsson et al., 1954; Sheiham & James, 2015). This temporal dimension of sugar exposure has important implications for understanding how different consumption patterns—chronic daily intake versus acute episodic surges—may differentially affect oral health outcomes.

Halloween presents a distinctive epidemiological scenario in the context of pediatric oral health. During this holiday, children in the United States and increasingly in other Western nations accumulate substantial quantities of candy through trick-or-treating activities, with estimates suggesting average hauls of 3-5 kilograms per child representing thousands of grams of added sugars (National Confectioners Association, 2021; TODO: verify estimate). This candy is typically consumed over a concentrated period of days to weeks following October 31st, creating a temporal pattern of sugar exposure that differs markedly from habitual daily consumption. The candy types distributed during Halloween span multiple product categories with distinct physical and chemical properties: chocolate bars and confections, gummy and sticky candies (bears, worms, fruit snacks), hard candies (lollipops, candy canes, butterscotch discs), and sour candies (sour gummies, sour belts, citric acid-coated products).

Despite the cultural ubiquity of Halloween candy consumption and the well-established role of sugar in caries pathogenesis, no published study has systematically compared the cariogenic potential of these different candy categories using computational or empirical methods. The existing literature on sugar and dental caries has predominantly focused on chronic dietary patterns—daily consumption of sugar-sweetened beverages, routine snacking behaviors, and long-term sugar exposure—rather than acute, episodic high-sugar events (Achalu et al., 2020; Inchingolo et al., 2023; Opinya, 2018). This gap is particularly striking given that dental professionals routinely provide guidance to parents regarding "safer" candy choices during Halloween, often recommending chocolate over sticky or sour varieties based on theoretical considerations of oral clearance time and adhesiveness (American Dental Association, 2020; TODO: verify specific ADA guidance).

The physical and chemical properties of different candy types suggest plausible mechanisms for differential cariogenicity. Chocolate, with its high fat content and melting point near oral temperature (37°C), may clear the oral cavity more rapidly due to fat-mediated lubrication and lower adhesion to tooth surfaces (Bhattacharyya & Joshi, 2022). Gummy and sticky candies, composed primarily of gelatin, starch, and concentrated sugars, exhibit high adhesiveness and prolonged oral retention, potentially sustaining elevated sugar concentrations in dental plaque for extended periods. Hard candies dissolve slowly through saliva-mediated erosion but maintain low adhesiveness, while sour candies introduce exogenous organic acids (citric, malic, tartaric) that directly lower oral pH independent of bacterial fermentation, potentially compounding cariogenic risk through combined erosive and cariogenic mechanisms (Lussi et al., 2004; TODO: verify citation).

Computational modeling approaches offer a methodologically rigorous framework for comparing cariogenic potential across candy types without requiring extensive clinical trials or in vivo studies. By integrating established oral physiology parameters—including salivary flow rates, bacterial fermentation kinetics, and pH buffering dynamics—with candy-specific physical properties such as dissolution rates and adhesiveness indices, simulation models can generate quantitative predictions of acid exposure profiles and demineralization risk (Dawes, 2008; TODO: verify citation). Such models build upon the foundational Stephan curve framework, which describes the temporal dynamics of plaque pH following sugar exposure, and extend this framework to incorporate candy matrix effects and multi-component oral clearance processes (Stephan, 1944; TODO: verify citation).

This study addresses the identified gap through a computational cariogenicity simulation comparing four Halloween candy categories. The research question guiding this investigation is: To what extent do different candy types commonly distributed at Halloween (chocolate, gummy/sticky candies, hard candies, sour candies) differ in their predicted cariogenic and erosive potential based on computational modeling of sugar release kinetics, oral retention time, and acidogenic pH profiles? The study tests the hypothesis that candy types with higher adhesiveness and prolonged oral retention (gummy/sticky candies) will exhibit greater cariogenic potential than rapidly cleared varieties (chocolate), with sour candies presenting elevated risk due to combined sugar content and exogenous acid exposure.

The significance of this research extends beyond Halloween-specific concerns to broader questions about how food matrix properties and consumption patterns interact to shape oral health outcomes. Understanding candy-type-specific cariogenic risk profiles could inform more nuanced public health messaging, guide parental decision-making during high-sugar holidays, and contribute to the development of evidence-based dietary recommendations that account for both sugar quantity and delivery matrix characteristics. Furthermore, the computational framework developed in this study establishes a reproducible methodology applicable to other episodic high-sugar consumption events and confectionery product categories, advancing the field toward more sophisticated caries risk assessment tools that incorporate food science parameters alongside traditional nutritional metrics.

## Review

### Sugar Consumption and Dental Caries: Established Evidence Base

The scientific foundation linking dietary sugar to dental caries rests upon decades of epidemiological, experimental, and mechanistic research. The Vipeholm study, conducted in Sweden between 1945 and 1953, provided seminal evidence that sugar consumption frequency and physical form (sticky versus non-sticky) significantly influenced caries incidence, establishing the principle that retention time and exposure frequency are critical modifiers of cariogenic risk (Gustafsson et al., 1954; TODO: verify citation details). Subsequent research has consistently demonstrated that populations with high sugar consumption exhibit elevated caries prevalence, with dose-response relationships observed across diverse geographic and cultural contexts (Moynihan & Kelly, 2014; Sheiham & James, 2015).

Contemporary systematic reviews and meta-analyses have reinforced these foundational findings while refining understanding of threshold effects and population-level recommendations. The World Health Organization's guideline recommending reduction of free sugar intake to less than 10% of total energy, with conditional recommendation for further reduction to less than 5%, is grounded in evidence linking sugar quantity to caries outcomes across age groups (WHO, 2015; TODO: verify year). Research by Moynihan and Kelly (2014) demonstrated that even at sugar intakes below 10% of energy, further reductions to 5% were associated with decreased caries incidence, suggesting no safe threshold for sugar consumption in caries prevention.

The mechanistic pathway from sugar consumption to enamel demineralization involves bacterial fermentation of fermentable carbohydrates to organic acids, primarily lactic acid, which lowers plaque pH below the critical threshold for hydroxyapatite dissolution (approximately pH 5.5) (Featherstone, 2000; Zero, 2004). The Stephan curve, first described in 1944, characterizes the temporal pattern of plaque pH decline following sugar exposure, with pH typically reaching a nadir within 5-15 minutes and recovering to baseline over 30-60 minutes depending on salivary buffering capacity and sugar quantity (Stephan, 1944; TODO: verify citation). The area under the pH curve below the critical threshold—termed the "demineralization window"—represents the cumulative acid exposure driving net mineral loss from enamel (Fejerskov, 2004; TODO: verify citation).

### Early Childhood Caries and Dietary Patterns

Early childhood caries (ECC), defined as the presence of one or more decayed, missing, or filled tooth surfaces in children under 71 months of age, represents a severe manifestation of diet-related caries with significant public health implications (American Academy of Pediatric Dentistry, 2020; TODO: verify citation). Research on ECC has identified specific dietary patterns associated with elevated risk, including prolonged bottle-feeding with sugar-containing liquids, frequent consumption of sugar-sweetened beverages, and habitual snacking on cariogenic foods (Achalu et al., 2020; Inchingolo et al., 2023; Opinya, 2018).

The literature on ECC emphasizes the role of feeding practices and parental behaviors in shaping children's oral health outcomes. Studies have demonstrated that parental knowledge, attitudes, and mediation strategies regarding sugar consumption significantly influence children's caries risk (Lumsden et al., 2023; Aguirre, 2022). Community-based intervention programs delivered by community health workers have shown effectiveness in reducing ECC incidence through education on dietary modification and oral hygiene practices, particularly in underserved populations experiencing health disparities (Lumsden et al., 2023).

However, the ECC literature has predominantly focused on chronic, habitual dietary patterns rather than episodic high-sugar events. Research examining sugar-sweetened beverage consumption, for example, typically assesses daily or weekly intake frequency as the exposure variable, treating sugar consumption as a relatively stable behavioral characteristic (Inchingolo et al., 2023). This approach, while appropriate for understanding long-term caries risk, provides limited insight into how acute sugar surges—such as those occurring during Halloween—may affect oral health outcomes in the short term or contribute to cumulative caries progression.

### Social Determinants and Oral Health Disparities

A substantial body of research documents the intersection of socioeconomic factors with oral health outcomes, revealing persistent disparities in caries prevalence among vulnerable populations. Food insecurity, poverty, limited access to dental care, and structural marginalization compound the effects of poor diet, producing elevated caries burden among Indigenous communities, migrant farmworker families, and populations in low-resource settings (Soares et al., 2021; Serna, 2014; Shomuyiwa & Bridge, 2023; Achalu et al., 2020).

These social determinants operate through multiple pathways, including constrained food choices, limited preventive care access, and environmental factors that shape dietary behaviors from early childhood. Research by Soares et al. (2021) examining oral health in Brazilian populations demonstrated that socioeconomic marginalization was independently associated with caries experience even after controlling for sugar consumption frequency, suggesting that structural factors modify the relationship between diet and oral health outcomes. Similarly, studies of Indigenous communities in North America have documented caries prevalence rates two to three times higher than national averages, attributed to complex interactions of historical trauma, food sovereignty loss, and contemporary food environment constraints (Shomuyiwa & Bridge, 2023).

The implications of these disparities for understanding Halloween candy consumption remain unexplored. It is unknown whether children from food-insecure or low-income households experience differential dental health impacts from seasonal candy surges, whether parental mediation strategies vary by socioeconomic status, or whether Halloween candy consumption exacerbates existing oral health inequities. These questions represent important directions for future research that would require integration of nutritional epidemiology with social determinants frameworks.

### Oral Microbiome and Dietary Perturbations

Advances in molecular microbiology and high-throughput sequencing have enabled detailed characterization of the oral microbiome and its responses to dietary exposures. The oral cavity harbors diverse microbial communities that form complex biofilms on tooth surfaces (dental plaque), with community composition influenced by host factors, oral hygiene practices, and dietary patterns (Zaura et al., 2020). Cariogenic bacteria including *Streptococcus mutans*, *Streptococcus sobrinus*, and various lactobacilli species are acidogenic and aciduric, thriving in low-pH environments and contributing to the positive feedback loop of demineralization and ecological shift toward cariogenic communities (Takahashi & Nyvad, 2011; TODO: verify citation).

Methodological guidance for designing rigorous oral microbiome studies has been established, including protocols for sample collection, DNA extraction, 16S rRNA gene sequencing, and bioinformatic analysis (Zaura et al., 2020). These methods enable investigation of microbial community shifts in response to dietary interventions, providing insights into how specific foods or consumption patterns alter the oral ecosystem. Emerging research has also explored natural antimicrobial agents, such as certain honey varieties, that may modulate oral biofilms and potentially counteract cariogenic processes (Silva et al., 2022).

Despite these methodological advances, no study has applied oral microbiome sequencing to track acute microbial community changes during and after concentrated candy consumption events such as Halloween. The temporal dynamics of microbiome perturbation and recovery following episodic high-sugar exposure remain unknown, representing a significant gap in understanding how holiday-associated dietary patterns may influence oral ecological balance and caries risk trajectories.

### Food Matrix Effects and Cariogenicity

The concept that food matrix properties—the physical and chemical characteristics of the food vehicle delivering sugars to the oral environment—influence cariogenic potential has been recognized but insufficiently studied. Early observations from the Vipeholm study suggested that sticky, retentive sweets produced greater caries incidence than non-sticky varieties at equivalent sugar doses, providing initial evidence for matrix effects (Gustafsson et al., 1954; TODO: verify citation). Subsequent research on specific foods has demonstrated that starch-containing foods, despite lower sugar content, may contribute to caries risk through prolonged retention and gradual enzymatic breakdown to fermentable sugars (Lingström et al., 2000; TODO: verify citation).

Food science research on confectionery products has characterized physical properties relevant to oral processing, including dissolution rates, melting behavior, and rheological properties under various temperature and mechanical stress conditions. Studies on chocolate rheology have demonstrated complex phase transition behavior as chocolate melts from solid to liquid state under thermal and deformation fields, with implications for oral clearance dynamics (Bhattacharyya & Joshi, 2022). Spectroscopic analysis of chocolate composition has revealed distinct sugar crystallization states and fat phase distributions that may influence sugar availability and release kinetics in the oral environment (He & Voronine, 2016).

Research on sugar alcohols and alternative sweeteners has provided comparative data on how different sweetening agents differ in their metabolic fate and cariogenic potential, with polyols such as xylitol and erythritol showing reduced or non-cariogenic properties compared to sucrose (Grembecka, 2015; TODO: verify citation). However, these studies have not systematically compared the cariogenicity of different candy matrices containing equivalent sugar quantities, leaving a gap in understanding how physical form factors modulate cariogenic risk.

### Identified Research Gaps

The literature review reveals several critical gaps that this study addresses. First, no published research has specifically examined Halloween candy consumption—or any analogous seasonal, holiday-associated sugar surge—and its effects on children's dental health outcomes. Second, the temporal dynamics of episodic high-sugar exposure versus chronic daily intake have not been systematically compared, leaving unclear whether concentrated candy consumption produces distinct cariogenic risk profiles. Third, different candy types commonly distributed during Halloween have not been differentially assessed for cariogenic potential despite plausible mechanistic differences in oral retention, dissolution kinetics, and acid exposure patterns. Fourth, no study has employed computational modeling approaches to integrate candy-specific physical properties with oral physiology parameters for quantitative cariogenicity prediction.

These gaps collectively represent a missed opportunity to provide evidence-based guidance for parents, dental professionals, and public health practitioners seeking to minimize caries risk during high-sugar holidays. The present study addresses these gaps through computational simulation comparing cariogenic and erosive potential across four major Halloween candy categories, establishing a methodological framework for candy-type-specific risk assessment.

## Methodology

### Study Design and Rationale

This study employed a computational simulation approach to compare the predicted cariogenic and erosive potential of four Halloween candy categories: chocolate, gummy/sticky candies, hard candies, and sour candies. The computational design was selected based on several considerations. First, clinical trials examining candy-type-specific caries incidence would require large sample sizes, extended follow-up periods, and complex ethical considerations regarding deliberate caries induction in pediatric populations. Second, in vitro studies using extracted teeth or enamel specimens, while methodologically feasible, would require specialized laboratory infrastructure and standardized protocols not readily available. Third, computational modeling enables systematic exploration of parameter space, sensitivity analysis, and hypothesis generation that can guide future empirical studies.

The simulation framework integrated three coupled components: (1) a candy product database with nutritional composition and physical property parameters, (2) a sugar release and oral clearance model incorporating candy matrix effects, and (3) a plaque pH dynamics model based on modified Stephan curve kinetics. This integrated approach enabled prediction of cariogenicity metrics for individual candy products and statistical comparison across candy type categories.

### Data Sources and Product Database Construction

The study planned to construct a structured dataset of candy products from two publicly available nutritional databases: USDA FoodData Central and Open Food Facts. USDA FoodData Central is a comprehensive U.S. government nutritional database containing detailed nutrient profiles for thousands of food products, including branded and generic candy items, with data on total sugars, sugar subtypes (sucrose, glucose, fructose where available), fat, protein, moisture, and carbohydrate composition (USDA, 2023; TODO: verify access date). Open Food Facts is a collaborative open database with nutritional information for hundreds of thousands of products worldwide, including many branded Halloween candy items, accessible through downloadable datasets and application programming interfaces (Open Food Facts, 2023; TODO: verify access date).

The planned data collection protocol involved searching both databases using keywords including "chocolate candy," "gummy candy," "hard candy," "sour candy," "caramel," "jelly bean," "lollipop," "candy bar," and "Halloween candy." Products were to be filtered to retain those with complete nutritional data and assigned to one of four candy type categories based on product name, description, and ingredient list. A minimum target of 15 products per category (60+ total) was established to enable meaningful between-group statistical comparisons.

For each product, the following nutritional features were to be extracted: total sugars (grams per 100 grams), sucrose/glucose/fructose composition where available, total fat, protein, moisture content, and carbohydrate type. Additionally, serving size information was to be recorded to enable calculation of sugar exposure per typical consumption event.

### Physical Property Parameter Assignment

Each candy type category was to be assigned physical property parameters derived from published food science and dental literature, representing characteristics relevant to oral processing and sugar release dynamics. These parameters included dissolution rate constant (k_diss, min⁻¹), adhesiveness index (dimensionless, 0-1 scale), estimated oral retention time (minutes), and initial sugar bolus release fraction.

Chocolate products were to receive parameters reflecting rapid melting at oral temperature (37°C) and fat-mediated oral clearance, based on rheological characterization studies demonstrating time-dependent phase transition behavior under thermal and mechanical stress (Bhattacharyya & Joshi, 2022). The high fat content of chocolate (typically 25-35% by weight) was expected to promote lubrication and reduce adhesion to tooth surfaces, facilitating more rapid clearance compared to low-fat confections.

Gummy and sticky candies were to be assigned high adhesiveness indices and slow dissolution rate constants, reflecting their gelatin- and starch-based matrices that adhere to tooth surfaces and require extended mastication and salivary dissolution. These products typically contain minimal fat (less than 1% by weight) and high sugar concentrations (50-70% by weight), creating conditions for prolonged sugar retention in the oral cavity.

Hard candies were to receive slow dissolution rate constants but low adhesiveness indices, representing their gradual erosion through saliva-mediated dissolution without significant tooth surface adhesion. These products are typically composed almost entirely of sugars (95%+ by weight) with minimal moisture and fat, dissolving over extended periods through continuous licking or sucking behaviors.

Sour candies were to be assigned moderate dissolution parameters plus an additional parameter representing exogenous organic acid content (citric, malic, or tartaric acid), which directly lowers oral pH independent of bacterial fermentation. The acid content parameter was to be estimated from ingredient lists and typical formulation concentrations reported in food science literature (TODO: specific values pending literature compilation).

### Computational Simulation Model

The computational simulation modeled three coupled processes over a 60-minute post-consumption window at 1-minute temporal resolution: sugar release kinetics, oral sugar concentration dynamics, and plaque pH responses.

**Sugar Release Module.** The sugar release process was modeled as a first-order dissolution process modulated by candy matrix properties and adhesiveness. The cumulative sugar released into the oral environment at time t was calculated as:

S(t) = S₀ × (1 - exp(-k_diss × t)) × (1 - A × exp(-k_clear × t))

where S₀ represents total available sugar in the serving (grams), k_diss is the candy-type-specific dissolution rate constant, A is the adhesiveness-modulated retention factor (dimensionless, 0-1), and k_clear is the salivary clearance rate constant. This formulation captures the initial rapid release of surface sugar followed by slower release from the candy matrix, with adhesive products retaining a fraction of sugar on tooth surfaces beyond the primary dissolution phase.

**Oral Sugar Concentration Module.** The oral sugar concentration at each time point was calculated by dividing available sugar by the oral fluid volume, accounting for stimulated salivary flow:

C(t) = S(t) / V_saliva(t)

where V_saliva(t) represents the cumulative oral fluid volume incorporating both unstimulated baseline salivary flow (approximately 0.3 mL/min) and stimulated flow (approximately 1.5 mL/min) triggered by sugar presence and mastication. The stimulated flow rate was modeled as increasing proportionally to sugar concentration, reflecting physiological salivary reflex responses.

**pH Dynamics Module.** Plaque pH dynamics were modeled using a modified Stephan curve framework that converts available sugar concentration to acid production via bacterial fermentation kinetics, buffered by salivary bicarbonate:

pH(t) = pH_resting - ΔpH_max × [C(t) / (K_m + C(t))] + recovery(t)

where pH_resting is the baseline plaque pH (approximately 6.8), ΔpH_max is the maximum achievable pH drop, K_m is the Michaelis-Menten half-saturation constant for bacterial sugar fermentation (estimated at 5.0 g/L based on TODO: verify literature source), and recovery(t) models bicarbonate buffering with exponential return toward resting pH. The critical demineralization threshold was set at pH 5.5 for enamel, consistent with established thermodynamic calculations for hydroxyapatite solubility (Featherstone, 2000; TODO: verify citation).

The model incorporated exogenous acid contributions for sour candies through an additional pH depression term representing direct acid exposure independent of bacterial metabolism. This term was parameterized based on estimated acid content and typical organic acid pKa values.

### Cariogenicity Metrics

Four primary cariogenicity metrics were to be computed from the simulated pH-time curves for each candy product:

1. **Time below critical pH (minutes):** The cumulative duration during which plaque pH remained below the critical threshold of 5.5, representing the total demineralization window.

2. **Area under the pH deficit curve (pH-minutes):** The integral of (5.5 - pH) over time when pH was below 5.5, representing cumulative acid exposure magnitude weighted by both duration and intensity.

3. **Minimum pH nadir:** The lowest pH value reached during the simulation, indicating maximum acid challenge intensity.

4. **Cumulative acid exposure index:** A time-weighted average of hydrogen ion concentration above baseline, calculated by integrating the difference between instantaneous H⁺ concentration and resting H⁺ concentration over the 60-minute period.

An additional erosive potential index was to be computed for sour candies, incorporating the exogenous acid contribution as a multiplier on the pH deficit metric to capture combined erosive and cariogenic mechanisms.

### Statistical Analysis Plan

Between-group differences across the four candy types were to be tested using one-way analysis of variance (ANOVA) for each of the four cariogenicity metrics, with significance set at α = 0.05. Post-hoc pairwise comparisons were to be conducted using Tukey's Honestly Significant Difference (HSD) test to control family-wise error rate while maintaining statistical power for multiple comparisons.

Effect sizes were to be reported as Cohen's d for all pairwise comparisons, with conventional thresholds of 0.2, 0.5, and 0.8 representing small, medium, and large effects respectively (Cohen, 1988; TODO: verify citation). Non-parametric Kruskal-Wallis tests were planned as alternative analyses if normality assumptions were violated, assessed through Shapiro-Wilk tests and visual inspection of residual distributions.

Bonferroni correction for multiple comparisons across the four metrics was to be applied, adjusting the significance threshold to α = 0.0125 for individual metric tests to maintain overall Type I error rate at 0.05.

### Sensitivity Analysis

Sensitivity analysis was planned to assess the robustness of findings to uncertainty in key model parameters. Parameters to be varied included dissolution rate constants (±50% of base values), adhesiveness indices (±0.1 absolute), salivary flow rates (unstimulated: 0.2-0.5 mL/min; stimulated: 1.0-2.0 mL/min), and bacterial fermentation parameters (K_m: 3-8 g/L; V_max: ±30% of base value). For each parameter variation, the complete simulation was to be re-run and candy type rankings compared to assess whether rank order inversions occurred under plausible parameter uncertainty.

The sensitivity analysis was designed to identify which parameters most strongly influenced cariogenicity predictions and to quantify the confidence intervals around predicted rankings, providing transparency regarding model limitations and areas requiring empirical parameter refinement.

### Validation Approach

Given the absence of ground-truth clinical cariogenicity datasets for these specific candy categories, validation was to proceed through multiple complementary approaches:

1. **Internal consistency checks:** Higher sugar products within a category should yield equal or higher cariogenicity scores, providing face validity for the dose-response relationship.

2. **Comparison with dental health guidance:** Predicted rankings were to be compared against established dental association recommendations regarding candy types (e.g., American Dental Association guidance suggesting chocolate as preferable to sticky candies), assessing whether model outputs align with expert consensus (TODO: verify specific ADA guidance).

3. **Physiological plausibility assessment:** Simulated pH curves were to be evaluated for consistency with published Stephan curve observations, including minimum pH values between 4.0 and 6.5, recovery to near-resting pH within 30-60 minutes, and realistic temporal dynamics (Stephan, 1944; TODO: verify citation).

4. **Literature comparison:** Where available, predicted cariogenicity rankings were to be compared against any in vitro or in vivo cariogenicity data from the broader dental literature, though the literature review indicated such comparative data were limited or absent for these specific candy categories.

### Software and Computational Environment

The simulation was to be implemented in Python using standard scientific computing libraries: NumPy for numerical operations, SciPy for differential equation solving and statistical functions, pandas for data manipulation, matplotlib for visualization, and statsmodels for advanced statistical analyses including Tukey HSD tests. The computational requirements were modest, requiring only standard desktop computing resources without specialized hardware or large-scale compute infrastructure.

## Results

**Status: Pending — Experimental Execution Not Completed**

The computational simulation described in the Methodology section was not executed due to infrastructure limitations within the automated research pipeline. The experiment specification required a custom computational runner capable of executing multi-phase simulation workflows involving database queries, numerical modeling, and statistical analysis—capabilities beyond the standard tabular data processing runners available in the current pipeline architecture.

Specifically, the experiment was designated as requiring a "NEEDS_NEW_RUNNER" configuration, indicating that specialized execution infrastructure would need to be developed to support the computational cariogenicity simulation. The automated Experiment Agent, configured to execute universal tabular CSV and universal data file specifications, was unable to process the custom simulation workflow involving coupled ordinary differential equations, iterative numerical integration, and multi-metric cariogenicity computation.

As a result, no empirical results were generated, and the planned statistical analyses comparing cariogenicity metrics across candy types were not performed. The hypothesis regarding differential cariogenic potential (gummy/sticky > sour > hard > chocolate) remains untested pending successful execution of the computational simulation.

### Planned Analytical Outputs

Had the simulation been executed, the following analytical outputs would have been generated:

1. **Descriptive statistics:** Mean and standard deviation for each cariogenicity metric (time below pH 5.5, area under pH deficit curve, pH nadir, cumulative acid exposure) stratified by candy type, presented in tabular format.

2. **Inferential statistics:** One-way ANOVA F-statistics and p-values for each metric, Tukey HSD post-hoc comparison results with confidence intervals, and Cohen's d effect sizes for all pairwise candy type comparisons.

3. **Visualizations:** Time-series plots of simulated pH curves for representative products from each candy category, overlaid on a single figure with the critical pH 5.5 threshold marked; bar charts comparing mean cariogenicity metrics across candy types with error bars representing standard deviations; and sensitivity analysis plots showing how predicted rankings varied across parameter uncertainty ranges.

4. **Candy type rankings:** Ordered rankings from highest to lowest cariogenic potential for each metric, with statistical significance of pairwise differences indicated.

5. **Sensitivity analysis results:** Quantification of ranking stability across parameter variations, identification of parameters most influential in determining cariogenicity predictions, and confidence intervals around predicted rankings.

### Data Availability

The planned data sources (USDA FoodData Central and Open Food Facts) remain publicly accessible, and the computational model specification provided in the Methodology section contains sufficient detail to enable independent replication by researchers with appropriate computational infrastructure. The Python implementation code, while not executed in this study, could be developed based on the mathematical formulations and parameter specifications described above.

## Discussion

### Interpretation of Planned Findings

The inability to execute the computational simulation represents a significant limitation of this study, preventing empirical testing of the hypothesis that different Halloween candy types exhibit differential cariogenic potential based on their physical and chemical properties. However, the methodological framework developed herein provides several insights into the theoretical basis for candy-type-specific cariogenicity and identifies critical parameters requiring empirical investigation.

The hypothesized ranking of cariogenic potential (gummy/sticky > sour > hard > chocolate) is grounded in established principles of oral physiology and food science. Gummy and sticky candies, with their high adhesiveness and prolonged oral retention, would theoretically sustain elevated sugar concentrations in dental plaque for extended periods, maximizing the duration of acid production by cariogenic bacteria. This prediction aligns with historical observations from the Vipeholm study suggesting that sticky, retentive sweets produced greater caries incidence than non-sticky varieties (Gustafsson et al., 1954; TODO: verify citation), and with contemporary dental health guidance recommending avoidance of sticky candies for caries prevention (TODO: verify specific guidance sources).

Sour candies present a unique risk profile combining high sugar content with exogenous organic acids that directly lower oral pH independent of bacterial fermentation. The dual mechanism of acid exposure—exogenous acids creating immediate pH depression followed by bacterial fermentation of sugars sustaining acid production—would theoretically produce larger areas under the pH deficit curve and more prolonged demineralization windows compared to non-acidic candies with equivalent sugar content. This prediction is consistent with research on acidic beverages demonstrating that low pH drinks cause enamel erosion even in the absence of bacterial metabolism (Lussi et al., 2004; TODO: verify citation).

Hard candies, despite their slow dissolution rates and high sugar content, were hypothesized to present moderate cariogenic risk due to low adhesiveness, allowing salivary clearance to more effectively remove dissolved sugars from tooth surfaces. The continuous stimulation of salivary flow during prolonged hard candy consumption would enhance buffering capacity and accelerate pH recovery, potentially limiting cumulative acid exposure despite extended consumption duration.

Chocolate was predicted to exhibit the lowest cariogenic potential among the four categories, attributed to its high fat content promoting oral lubrication and rapid clearance, combined with melting behavior at oral temperature that reduces retention on tooth surfaces. The rheological properties of chocolate, including its phase transition from solid to liquid state under thermal and mechanical stress (Bhattacharyya & Joshi, 2022), would theoretically facilitate more complete oral clearance compared to low-fat confections that adhere to tooth surfaces.

### Methodological Considerations and Limitations

The computational modeling approach employed in this study offers several advantages, including systematic exploration of parameter space, ability to isolate specific mechanisms (e.g., adhesiveness effects independent of sugar quantity), and generation of quantitative predictions without requiring clinical trials. However, the approach also entails significant limitations that must be acknowledged.

First, the model necessarily simplifies the complex oral environment, representing average physiological parameters rather than capturing individual variation in salivary composition, oral microbiome composition, tooth surface topography, and eating behaviors. Real-world candy consumption involves heterogeneous chewing patterns, variable oral retention times, and individual differences in salivary flow rates and buffering capacity that would produce substantial variation in actual cariogenic responses.

Second, the physical property parameters assigned to each candy type (dissolution rates, adhesiveness indices) were estimated from limited food science literature and expert judgment rather than measured under controlled oral-simulated conditions. The literature review revealed that empirical data on candy dissolution kinetics and oral retention under standardized conditions were largely absent, requiring parameter estimation that introduces uncertainty into model predictions. Future research should prioritize empirical measurement of these parameters using in vitro oral simulation systems or in vivo studies with controlled candy consumption protocols.

Third, the model assumes a single consumption event and does not account for repeated candy consumption over time, as typically occurs during the post-Halloween period when children consume accumulated candy over days to weeks. Repeated consumption events would compound acid exposure and potentially alter oral microbiome composition through selective pressure favoring aciduric bacterial species, effects not captured in the single-event simulation framework.

Fourth, the validation approach was necessarily limited by the absence of ground-truth clinical data linking specific candy types to caries incidence. While face validity against dental health guidance and physiological plausibility checks provide some confidence in model outputs, empirical validation through clinical or in vitro studies would substantially strengthen the evidence base for candy-type-specific cariogenicity predictions.

### Implications for Public Health and Clinical Practice

If the hypothesized candy type rankings were empirically confirmed, the findings would have direct implications for public health messaging and clinical guidance around Halloween and similar high-sugar holidays. Dental professionals could provide more nuanced recommendations to parents, suggesting preference for chocolate over gummy or sour candies when candy consumption is anticipated, and emphasizing the importance of oral hygiene practices following consumption of high-retention candy types.

Public health campaigns could incorporate candy-type-specific guidance alongside traditional messages about limiting overall sugar quantity, recognizing that the delivery matrix and physical properties of sugary foods modulate cariogenic risk independent of sugar content alone. Such messaging would align with broader nutrition science trends emphasizing food matrix effects and moving beyond simplistic nutrient-focused dietary guidelines.

For parents, evidence-based candy type guidance could inform decision-making about candy rationing, substitution, or selective removal strategies during the post-Halloween period. Some families have adopted "candy buyback" programs where parents purchase Halloween candy from children, often donating it to charitable organizations—such programs could be refined to preferentially remove high-cariogenicity candy types (gummy, sour) while allowing limited consumption of lower-risk varieties (chocolate).

### Directions for Future Research

The methodological framework developed in this study establishes a foundation for multiple future research directions. First, empirical execution of the computational simulation using the specified model and publicly available nutritional databases would generate the planned cariogenicity predictions and enable hypothesis testing. This requires development of custom computational infrastructure capable of executing the multi-phase simulation workflow.

Second, empirical measurement of candy-specific physical properties under oral-simulated conditions would provide more accurate parameter values for the computational model. In vitro studies using artificial saliva systems, controlled temperature and mechanical stress conditions, and systematic measurement of dissolution rates and adhesiveness for representative products from each candy category would substantially reduce parameter uncertainty.

Third, clinical studies examining actual oral pH responses to different candy types using intraoral pH sensors would provide direct validation of the computational model predictions. Such studies, while methodologically challenging, would generate ground-truth data on candy-type-specific Stephan curves and enable refinement of model parameters based on empirical observations.

Fourth, longitudinal epidemiological studies tracking children's oral health outcomes following Halloween candy consumption, with detailed assessment of candy types consumed and post-consumption oral hygiene practices, would provide population-level evidence on the real-world impact of episodic high-sugar events on caries progression. Integration of such data with socioeconomic variables would enable investigation of whether Halloween candy consumption exacerbates existing oral health disparities.

Fifth, oral microbiome studies applying 16S rRNA sequencing to track microbial community shifts before, during, and after concentrated candy consumption periods would provide insights into how episodic high-sugar events influence oral ecological balance and whether different candy types produce distinct microbiome perturbation signatures.

### Broader Significance

Beyond Halloween-specific applications, this research addresses fundamental questions about how food matrix properties and consumption patterns interact to shape oral health outcomes. The computational framework developed herein is applicable to other episodic high-sugar consumption events (birthday parties, holiday celebrations, sporting events) and could be extended to evaluate cariogenicity of diverse confectionery product categories beyond the four Halloween candy types examined.

The study also contributes to broader efforts to develop more sophisticated caries risk assessment tools that incorporate food science parameters alongside traditional nutritional metrics. Current dietary guidance for caries prevention focuses primarily on sugar quantity and consumption frequency, with limited attention to food matrix effects. The computational modeling approach demonstrated here provides a methodological template for integrating candy-specific physical properties with oral physiology parameters, advancing toward personalized caries risk prediction that accounts for both dietary patterns and food characteristics.

## Conclusion

This study addressed a critical gap in understanding the cariogenic potential of different Halloween candy types through development of a computational simulation framework integrating candy-specific physical properties with established oral physiology parameters. The methodological design compared four major candy categories—chocolate, gummy/sticky candies, hard candies, and sour candies—using a modified Stephan curve model incorporating sugar release kinetics, salivary clearance dynamics, and bacterial fermentation kinetics to predict cariogenicity metrics including time below critical pH, area under pH deficit curve, pH nadir, and cumulative acid exposure.

The study hypothesized that candy types with higher adhesiveness and prolonged oral retention would exhibit greater cariogenic potential, predicting a ranking from highest to lowest risk of: gummy/sticky > sour > hard > chocolate. This hypothesis was grounded in established principles of oral physiology and food science, with gummy/sticky candies expected to sustain elevated plaque sugar concentrations through prolonged retention, sour candies presenting dual risk through combined sugar content and exogenous acids, hard candies showing moderate risk due to slow dissolution but low adhesiveness, and chocolate exhibiting lowest risk due to fat-mediated rapid oral clearance.

However, experimental execution was not completed due to infrastructure limitations requiring custom computational runners beyond the available automated pipeline capabilities. As a result, the hypothesis remains untested, and no empirical cariogenicity predictions or statistical comparisons were generated. The methodological framework, computational model specification, and planned analytical approach are fully documented herein, establishing a reproducible protocol for future empirical investigation.

The study identifies several critical needs for advancing this research agenda: development of computational infrastructure capable of executing the specified simulation workflow, empirical measurement of candy-specific physical properties under oral-simulated conditions, clinical validation studies examining actual oral pH responses to different candy types, and longitudinal epidemiological research tracking caries outcomes following episodic high-sugar consumption events.

If successfully executed and validated, this research would provide evidence-based guidance for parents, dental professionals, and public health practitioners seeking to minimize caries risk during Halloween and similar high-sugar holidays. The findings would inform more nuanced dietary recommendations that account for food matrix effects alongside sugar quantity, contributing to more effective caries prevention strategies that recognize the complex interactions between food characteristics, consumption patterns, and oral physiology.

The broader significance extends beyond Halloween-specific applications to fundamental questions about how food matrix properties modulate cariogenic risk, establishing a methodological framework applicable to diverse confectionery products and episodic high-sugar consumption events. This work advances the field toward more sophisticated caries risk assessment tools that integrate food science parameters with oral biology, ultimately supporting personalized preventive strategies tailored to individual dietary patterns and food choices.

## Figure Generation Notes

### Figure 1: Simulated pH-Time Curves by Candy Type
**Description:** Time-series plot showing simulated plaque pH dynamics over 60 minutes following consumption of representative products from each candy category (chocolate, gummy/sticky, hard, sour). Four curves overlaid on single plot with critical pH 5.5 threshold marked as horizontal dashed line. X-axis: time (minutes, 0-60); Y-axis: pH (4.0-7.0). Each curve represents mean pH trajectory across products within category, with shaded regions indicating standard deviation.

**Data Source:** Computational simulation output (pending execution). Model parameters from USDA FoodData Central nutritional data and published oral physiology literature.

**Generation Prompt:** "Create a line plot with four curves representing pH over time (0-60 minutes) for four candy types: chocolate (blue), gummy/sticky (red), hard (green), sour (orange). Add horizontal dashed line at pH 5.5 labeled 'Critical pH for enamel demineralization'. Y-axis range 4.0-7.0, X-axis labeled 'Time (minutes)'. Include legend in upper right corner. Use smooth curves with shaded standard deviation bands."

### Figure 2: Comparison of Cariogenicity Metrics Across Candy Types
**Description:** Four-panel bar chart comparing mean values for each cariogenicity metric (time below pH 5.5, area under pH deficit curve, pH nadir, cumulative acid exposure) across four candy types. Error bars representing standard deviations. Statistical significance indicators (asterisks) for pairwise comparisons based on Tukey HSD results.

**Data Source:** Computational simulation output (pending execution).

**Generation Prompt:** "Create a 2x2 grid of bar charts. Each subplot shows four bars (chocolate, gummy/sticky, hard, sour) for one metric: (A) Time below pH 5.5 (minutes), (B) Area under pH deficit curve (pH-minutes), (C) pH nadir, (D) Cumulative acid exposure index. Include error bars for standard deviation. Add significance brackets with asterisks for p<0.05, p<0.01, p<0.001. Use consistent color scheme: chocolate=brown, gummy=red, hard=yellow, sour=green."

### Figure 3: Candy Type Ranking and Effect Sizes
**Description:** Horizontal bar chart showing cariogenicity ranking for each metric, with bar length representing mean metric value and error bars showing 95% confidence intervals. Adjacent table displaying Cohen's d effect sizes for all pairwise comparisons.

**Data Source:** Computational simulation statistical analysis output (pending execution).

**Generation Prompt:** "Create horizontal bar chart with four panels (one per metric). Each panel shows four horizontal bars ranked from highest to lowest cariogenicity. Include 95% CI error bars. Adjacent to chart, create table with rows showing pairwise comparisons (gummy vs sour, gummy vs hard, etc.) and columns showing Cohen's d values with color coding: light blue (d<0.2), medium blue (0.2-0.5), dark blue (0.5-0.8), navy (d>0.8)."

### Figure 4: Sensitivity Analysis of Parameter Uncertainty
**Description:** Tornado plot or spider plot showing how predicted candy type rankings change as key parameters (dissolution rate, adhesiveness, salivary flow, K_m) are varied across plausible ranges. Demonstrates robustness of findings to parameter uncertainty.

**Data Source:** Computational simulation sensitivity analysis output (pending execution).

**Generation Prompt:** "Create tornado plot showing sensitivity of cariogenicity ranking to parameter variations. Y-axis lists parameters (dissolution rate ±50%, adhesiveness ±0.1, saliva flow 0.2-2.0 mL/min, K_m 3-8 g/L). X-axis shows change in ranking position or metric value. Use diverging color scheme centered on base case. Include vertical line at zero change."

### Table 1: Candy Product Database Characteristics
**Description:** Summary statistics for nutritional composition and physical properties of candy products in each category (N=20 per category, 80 total). Columns: candy type, N, mean±SD for total sugars (g/100g), fat (g/100g), protein (g/100g), moisture (g/100g), dissolution rate (min⁻¹), adhesiveness index, serving size (g).

**Data Source:** Constructed dataset from USDA FoodData Central and Open Food Facts (pending data collection).

**Caption:** "Table 1. Nutritional composition and physical property parameters for candy products by category. Data compiled from USDA FoodData Central and Open Food Facts databases. Physical property parameters (dissolution rate, adhesiveness) estimated from food science literature and expert judgment."

### Table 2: Cariogenicity Metrics by Candy Type
**Description:** Mean±SD for each cariogenicity metric stratified by candy type, with ANOVA F-statistics, p-values, and effect sizes (Cohen's d) for pairwise comparisons.

**Data Source:** Computational simulation output (pending execution).

**Caption:** "Table 2. Comparison of cariogenicity metrics across four Halloween candy types. Values represent mean±standard deviation. F-statistics and p-values from one-way ANOVA. Effect sizes (Cohen's d) reported for all pairwise comparisons. Significant differences (p<0.05 after Bonferroni correction) indicated by superscript letters."

### Workflow Diagram: Computational Simulation Pipeline
**Description:** Flowchart illustrating the multi-phase computational simulation workflow: (1) Data compilation from USDA and Open Food Facts databases, (2) Candy type categorization and parameter assignment, (3) Numerical simulation of sugar release, oral concentration, and pH dynamics, (4) Metric computation and statistical analysis, (5) Sensitivity analysis and validation.

**Data Source:** Study design documentation.

**Generation Prompt:** "Create flowchart with five main boxes connected by arrows. Box 1: 'Data Compilation' with sub-bullets 'USDA FoodData Central' and 'Open Food Facts'. Box 2: 'Product Categorization' with sub-bullets 'Chocolate', 'Gummy/Sticky', 'Hard', 'Sour'. Box 3: 'Computational Simulation' with sub-bullets 'Sugar Release Model', 'Oral Concentration', 'pH Dynamics'. Box 4: 'Metric Computation' with sub-bullets 'Time below pH 5.5', 'AUC deficit', 'pH nadir', 'Acid exposure'. Box 5: 'Statistical Analysis' with sub-bullets 'ANOVA', 'Tukey HSD', 'Sensitivity analysis'. Use rounded rectangles, consistent color scheme, and clear directional arrows."

## References

Achalu, I. M., et al. (2020). [Title pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Aguirre, [Initials]. (2022). [Title regarding digital information landscape and early childhood caries pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

American Academy of Pediatric Dentistry. (2020). Policy on early childhood caries (ECC): Classifications, consequences, and preventive strategies. [URL pending verification]. TODO: Verify year and access details.

American Dental Association. (2020). [Halloween candy guidance document pending verification]. [URL pending verification]. TODO: Verify specific guidance and access date.

Bhattacharyya, [Initials], & Joshi, [Initials]. (2022). [Title regarding chocolate rheology and thermal/mechanical rejuvenation pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Cohen, J. (1988). Statistical power analysis for the behavioral sciences (2nd ed.). Lawrence Erlbaum Associates.

Dawes, C. (2008). [Title regarding salivary flow and oral clearance pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Featherstone, J. D. B. (2000). Dental caries: A dynamic disease process. Australian Dental Journal, 45(4), 228-235. TODO: Verify volume and pages.

Fejerskov, O. (2004). [Title regarding demineralization and caries mechanisms pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Grembecka, M. (2015). Sugar alcohols (polyols) as sweeteners. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Gustafsson, B. E., Quensel, C. E., Lanke, L. S., Lundqvist, C., Grahnen, H., Bonow, B. E., & Krasse, B. (1954). The Vipeholm dental caries study. Acta Odontologica Scandinavica, 11(3-4), 232-364. TODO: Verify volume and pages.

He, [Initials], & Voronine, [Initials]. (2016). [Title regarding Raman spectroscopy of chocolate pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Hofilena, [Initials]. (2015). [Title regarding vitamin D and dental health pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Inchingolo, F., et al. (2023). [Title regarding dietary patterns and early childhood caries pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Keyes, P. H. (1962). Research in dental caries. Journal of the American Dental Association, 76(4), 765-773. TODO: Verify volume and pages.

Lingström, P., van Houte, J., & Kashket, S. (2000). Food starches and dental caries. Critical Reviews in Oral Biology and Medicine, 11(4), 459-470. TODO: Verify volume and pages.

Lumsden, [Initials], et al. (2023). [Title regarding community health worker interventions for ECC pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Lussi, A., Jaeggi, T., & Zero, D. (2004). The role of diet in the aetiology of dental erosion. Caries Research, 38(3), 217-222. TODO: Verify volume and pages.

Mir, [Initials], et al. (2020). [Title regarding fluoride intake assessment pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Morgan, [Initials], et al. (2008). [Title regarding media exposure and confectionery advertising pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Moynihan, P. J., & Kelly, S. A. M. (2014). Effect on caries of restricting sugars intake: Systematic review to inform WHO guidelines. Journal of Dental Research, 93(1), 8-18.

National Confectioners Association. (2021). [Halloween candy consumption statistics pending verification]. [URL pending verification]. TODO: Verify specific statistics and access date.

Newbrun, E. (1982). Sugar and dental caries: A review of the evidence. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Opinya, [Initials]. (2018). [Title regarding dietary patterns and caries pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Open Food Facts. (2023). Open Food Facts database. Retrieved from https://world.openfoodfacts.org/data. TODO: Verify access date.

Petersen, P. E. (2003). The World Oral Health Report 2003: Continuous improvement of oral health in the 21st century—the approach of the WHO Global Oral Health Programme. Community Dentistry and Oral Epidemiology, 31(Suppl 1), 3-24.

Sheiham, A., & James, W. P. T. (2015). Diet and dental caries: The pivotal role of free sugars reemphasized. Journal of Dental Research, 94(10), 1341-1347.

Shomuyiwa, [Initials], & Bridge, [Initials]. (2023). [Title regarding Indigenous oral health disparities pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Silva, [Initials], et al. (2022). [Title regarding honey and oral biofilms pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Soares, [Initials], et al. (2021). [Title regarding socioeconomic factors and oral health in Brazil pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Somji, [Initials], et al. (2016). [Title regarding soda taxation and oral health pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Serna, [Initials]. (2014). [Title regarding migrant farmworker oral health pending verification]. [Journal pending verification], [Volume](Issue), [Pages]. TODO: Complete citation details.

Stephan, R. M. (1944).

## Automated Review Note
The live revision API was unavailable, so this draft has not been rewritten by the Review agent. The remaining weaknesses file lists the conservative local review findings.
