RESEARCH QUESTION:
How do the lyrical themes of Drake and Kendrick Lamar differ in their treatment of race, masculinity, and emotional vulnerability, and to what extent do these thematic differences correspond to distinct patterns of engagement and sentiment among self-identified white teenage users on public social media platforms such as Reddit and Twitter?

HYPOTHESIS:
Kendrick Lamar's discography exhibits significantly higher prevalence of systemic-race and collective-identity themes, whereas Drake's discography exhibits significantly higher prevalence of individualized emotional vulnerability and relational masculinity themes; furthermore, these thematic divergences correspond to measurably distinct reception patterns among self-identified white teenage social media users, such that Drake's content generates higher aggregate positive sentiment scores and greater engagement volume (upvotes, replies, shares) from this demographic, while Kendrick Lamar's content generates lower engagement volume but higher thematic-depth discourse (longer comment threads, greater use of sociopolitical vocabulary) among the same population.

ANALYSIS GOAL:
The analysis must determine (1) whether a systematic, replicable quantitative comparison of Drake's and Kendrick Lamar's lyrical corpora confirms statistically significant differences in the prevalence and framing of race, masculinity, and emotional vulnerability themes; (2) whether self-identified white teenage users on Reddit and Twitter/X exhibit measurably different sentiment distributions, engagement intensities, and discursive framing patterns when responding to content associated with each artist; and (3) whether specific lyrical theme categories (e.g., systemic racism critique, interpersonal vulnerability, hegemonic vs. alternative masculinity) can be statistically linked to corresponding patterns in audience engagement metrics and sentiment polarity, thereby establishing a correlational — though not causal — relationship between thematic content and cross-demographic reception.

REQUIRED DATA CHARACTERISTICS:
- **Lyrical corpus**: Complete studio album discographies of both Drake and Kendrick Lamar (minimum: all major-label studio albums through 2024), with full lyrical text available in machine-readable format, including song titles, album identifiers, and release dates.
- **Thematic annotation schema**: A validated or researcher-constructed coding scheme with clearly defined categories for (a) race-related content (individual vs. systemic framing, racial pride, racial injustice), (b) masculinity constructs (hegemonic, vulnerable, performative, relational), and (c) emotional vulnerability (self-disclosure of sadness, anxiety, insecurity, interpersonal conflict). Inter-coder reliability metrics (Cohen's kappa >= 0.70) must be achievable.
- **Social media data — Reddit**: Publicly accessible posts and comments from relevant subreddits (e.g., r/hiphopheads, r/Drake, r/KendrickLamar, r/teenagers, r/Music) containing references to Drake or Kendrick Lamar, with available metadata including author username, post/comment text, upvote/downvote counts, timestamps, and thread depth. Data must span a sufficient time window (minimum 24 months) to capture engagement trends across multiple album releases or cultural events (e.g., the 2024 Drake-Kendrick Lamar conflict documented by Linscott, 2025).
- **Social media data — Twitter/X**: Public tweets and replies mentioning Drake or Kendrick Lamar, with available metadata including author handle, tweet text, like/retweet/reply counts, and timestamps, over the same time window.
- **Demographic identification signal**: A method for identifying self-identified white teenage users (ages 13–19) through explicit self-disclosure in user bios, profile descriptions, subreddit flair, or post content (e.g., "17M" conventions on r/teenagers, age/race self-reports in comments). The dataset must contain a sufficient sample of such users (minimum N = 200 unique identifiable users across platforms) to enable statistical comparison.
- **Sentiment analysis capability**: An NLP pipeline capable of assigning sentiment polarity scores (positive, negative, neutral) and emotion classifications (joy, anger, sadness, fear, disgust) to social media text at the post/comment level, with validated accuracy on informal social media language.
- **Temporal alignment**: Lyrical release dates must be alignable with social media engagement timestamps to enable event-study or time-series analysis of audience response to specific songs, albums, or public events.

KEY VARIABLES:
- **Independent variables**:
  - Artist identity (Drake vs. Kendrick Lamar)
  - Lyrical theme category (systemic race, individualized race, hegemonic masculinity, vulnerable masculinity, relational masculinity, emotional vulnerability — self-disclosure, emotional vulnerability — interpersonal conflict)
  - Lyrical theme intensity score (continuous: frequency or density of theme-related language per song)
  - Release event type (studio album, single, diss track, featured verse, public statement)

- **Dependent variables**:
  - Social media sentiment polarity score (continuous, per post/comment)
  - Engagement volume (count: upvotes + replies + shares/retweets per post)
  - Thread depth (count: number of nested reply levels per discussion thread)
  - Thematic-depth discourse indicator (continuous: average word count per comment, frequency of sociopolitical vocabulary per thread)
  - Engagement rate ratio (Drake-engagement / Kendrick-engagement, computed per time window)

- **Control variables**:
  - Platform (Reddit vs. Twitter/X)
  - Subreddit or community context (music-focused vs. general-teen communities)
  - Temporal factors (days since release, proximity to major cultural events such as the 2024 beef)
  - User account age and prior posting frequency (to control for bot or lurker accounts)
  - Song popularity metrics (streaming counts or chart positions, to control for baseline exposure differences)
  - Lyrical complexity controls (song length, vocabulary diversity, featuring artists)

SUCCESS CRITERIA:
- **Lyrical analysis criterion**: A two-sample comparison of theme prevalence scores between Drake and Kendrick Lamar yields statistically significant differences (p < 0.05, with effect size Cohen's d >= 0.40) on at least two of the three thematic axes (race, masculinity, emotional vulnerability), confirming that the artists' lyrical content is quantitatively distinguishable along these dimensions.
- **Audience engagement criterion**: Sentiment polarity distributions and engagement volume metrics for self-identified white teenage users differ significantly between Drake-associated and Kendrick Lamar-associated content (p < 0.05, Mann-Whitney U or equivalent non-parametric test), with Drake content exhibiting higher median positive sentiment and engagement volume.
- **Thematic discourse criterion**: Kendrick Lamar-associated threads exhibit significantly greater mean comment length and higher frequency of sociopolitical vocabulary (p < 0.05) compared to Drake-associated threads among the same demographic, indicating deeper thematic engagement despite lower raw engagement volume.
- **Correlation criterion**: A Spearman or Pearson correlation analysis between lyrical theme intensity scores and corresponding social media engagement/sentiment metrics yields at least two statistically significant correlations (p < 0.05, |r| >= 0.30) across the thematic axes, establishing a meaningful associative link between specific lyrical content and audience response patterns.
- **Robustness criterion**: The above findings hold after controlling for platform, community context, temporal proximity to release events, and baseline song popularity, as confirmed through multivariate regression or stratified analysis.